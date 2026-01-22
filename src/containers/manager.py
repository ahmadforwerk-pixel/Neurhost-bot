"""Docker container management for user bots."""

import docker
from docker.types import RestartPolicy
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class DockerContainerManager:
    """
    Manage Docker containers for user bots.
    
    Security model:
    - Each bot in isolated container
    - Non-root user
    - Hard resource limits (kernel enforced)
    - Read-only root filesystem (except /tmp)
    """
    
    def __init__(self, docker_host: Optional[str] = None):
        """
        Initialize Docker container manager.
        
        Args:
            docker_host: Docker daemon URL (e.g., unix:///var/run/docker.sock)
        """
        try:
            if docker_host:
                self.client = docker.DockerClient(base_url=docker_host)
            else:
                self.client = docker.from_env()
            logger.info("Connected to Docker daemon")
        except Exception as e:
            logger.critical(f"Cannot connect to Docker daemon: {e}")
            raise
    
    def launch_bot_container(
        self,
        bot_id: int,
        bot_token: str,
        timeout_seconds: int,
        cpu_limit: str = "500m",
        memory_limit: str = "512m",
    ) -> str:
        """
        Launch user bot in isolated Docker container.
        
        Args:
            bot_id: Internal bot ID
            bot_token: Telegram token (plaintext, only in memory)
            timeout_seconds: Kill container after this many seconds
            cpu_limit: CPU quota (e.g., "500m" = 0.5 cores)
            memory_limit: RAM limit (e.g., "512m")
        
        Returns:
            Container ID
        
        Raises:
            docker.errors.DockerException on Docker error
        """
        
        container_name = f"neurhost-bot-{bot_id}"
        
        try:
            # Ensure image exists
            image_name = "neurhost-user-bot:latest"
            try:
                self.client.images.get(image_name)
            except docker.errors.ImageNotFound:
                logger.warning(f"Image {image_name} not found, pulling base image...")
                self.client.images.pull("python:3.11-slim")
            
            # Run container with strict security settings
            container = self.client.containers.run(
                image=image_name,
                name=container_name,
                detach=True,
                remove=False,
                
                # Environment (only bot token, nothing else)
                environment={
                    "BOT_TOKEN": bot_token,
                    "BOT_ID": str(bot_id),
                    "PYTHONUNBUFFERED": "1",
                },
                
                # Volumes (read-only code)
                volumes={
                    f"/neurhost/bots/{bot_id}/code": {
                        "bind": "/app",
                        "mode": "ro"
                    }
                },
                
                # Network (isolated)
                network_mode="none",
                ports={},
                
                # Security
                user="botuser:botgroup",
                cap_drop=["ALL"],
                security_opt=["no-new-privileges:true"],
                read_only=True,
                
                # Temporary space
                tmpfs={
                    "/tmp": "size=100m,noexec,nodev,nosuid"
                },
                
                # Resource limits (kernel enforced)
                cpu_quota=int(float(cpu_limit.rstrip('m')) * 1000),
                cpus=float(cpu_limit.rstrip('m')) / 1000,
                mem_limit=memory_limit,
                memswap_limit=memory_limit,
                
                # Timeout (hard deadline)
                timeout=timeout_seconds + 10,
                
                # Restart policy
                restart_policy=RestartPolicy(Name="no"),
                
                # Logging
                stdout=True,
                stderr=True,
                logs=False,
            )
            
            logger.info(
                f"Started container {container.id[:12]} for bot {bot_id} "
                f"(CPU: {cpu_limit}, RAM: {memory_limit}, Timeout: {timeout_seconds}s)"
            )
            
            return container.id
        
        except docker.errors.ImageNotFound:
            raise ValueError(f"Docker image not found: {image_name}")
        except docker.errors.APIError as e:
            logger.error(f"Docker API error: {e}")
            raise
        except Exception as e:
            logger.exception(f"Error launching container: {e}")
            raise
    
    def stop_bot_container(self, bot_id: int, timeout: int = 10) -> bool:
        """
        Stop container gracefully.
        
        Args:
            bot_id: Bot ID
            timeout: Seconds to wait before SIGKILL
        
        Returns:
            True if stopped, False if already stopped
        """
        container_name = f"neurhost-bot-{bot_id}"
        
        try:
            container = self.client.containers.get(container_name)
            
            if container.status == "running":
                logger.info(f"Stopping container {container.id[:12]}...")
                container.stop(timeout=timeout)
                
                # Clean up
                try:
                    container.remove()
                except Exception as e:
                    logger.warning(f"Could not remove container: {e}")
                
                return True
            else:
                logger.debug(f"Container already stopped: {container.status}")
                return False
        
        except docker.errors.NotFound:
            logger.debug(f"Container {container_name} not found")
            return False
        except Exception as e:
            logger.error(f"Error stopping container: {e}")
            raise
    
    def get_container_stats(self, bot_id: int) -> Dict:
        """
        Get CPU and memory usage for bot container.
        
        Returns:
            {
                "cpu_percent": 45.2,
                "memory_mb": 128.5,
                "status": "running"
            }
        """
        container_name = f"neurhost-bot-{bot_id}"
        
        try:
            container = self.client.containers.get(container_name)
            
            if container.status != "running":
                return {"status": container.status, "cpu_percent": 0, "memory_mb": 0}
            
            stats = container.stats(stream=False)
            cpu_percent = self._calculate_cpu_percent(stats)
            memory_mb = stats['memory_stats'].get('usage', 0) / 1024 / 1024
            
            return {
                "cpu_percent": cpu_percent,
                "memory_mb": memory_mb,
                "status": "running"
            }
        
        except docker.errors.NotFound:
            return {"status": "not_found", "cpu_percent": 0, "memory_mb": 0}
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {"status": "error", "cpu_percent": 0, "memory_mb": 0}
    
    def _calculate_cpu_percent(self, stats: dict) -> float:
        """Calculate CPU usage percentage."""
        try:
            cpu_stats = stats['cpu_stats']
            system_cpu_usage = cpu_stats['system_cpu_usage']
            container_cpu_usage = cpu_stats['cpu_usage']['total_usage']
            
            cpu_delta = container_cpu_usage - stats.get('precpu_stats', {}).get('cpu_usage', {}).get('total_usage', 0)
            system_delta = system_cpu_usage - stats.get('precpu_stats', {}).get('system_cpu_usage', 0)
            
            if system_delta == 0:
                return 0.0
            
            cpu_percent = (cpu_delta / system_delta) * 100.0
            return min(100.0, cpu_percent)
        except Exception:
            return 0.0
