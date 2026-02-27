"""System notification utilities for user awareness."""

import subprocess
import platform
import logging
from typing import Optional


logger = logging.getLogger(__name__)


class SystemNotifier:
    """
    Cross-platform system notification handler.
    Sends native OS notifications to alert users of pipeline events.
    """

    def __init__(self, enabled: bool = True, sound: bool = True):
        """
        Initialize the notifier.

        Args:
            enabled: Whether notifications are enabled
            sound: Whether to play notification sound
        """
        self.enabled = enabled
        self.sound = sound
        self.system = platform.system()

    def notify(
        self,
        title: str,
        message: str,
        subtitle: Optional[str] = None,
        sound_name: Optional[str] = None
    ) -> bool:
        """
        Send a system notification.

        Args:
            title: Notification title
            message: Notification message
            subtitle: Optional subtitle (macOS only)
            sound_name: Optional sound name (macOS: 'default', 'Glass', 'Hero', etc.)

        Returns:
            True if notification was sent successfully
        """
        if not self.enabled:
            logger.debug("Notifications disabled, skipping")
            return False

        try:
            if self.system == "Darwin":  # macOS
                return self._notify_macos(title, message, subtitle, sound_name)
            elif self.system == "Linux":
                return self._notify_linux(title, message)
            elif self.system == "Windows":
                return self._notify_windows(title, message)
            else:
                logger.warning(f"Notifications not supported on {self.system}")
                return False

        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            return False

    def _notify_macos(
        self,
        title: str,
        message: str,
        subtitle: Optional[str] = None,
        sound_name: Optional[str] = None
    ) -> bool:
        """Send notification on macOS using osascript."""
        # Build AppleScript command
        script_parts = [f'display notification "{message}"']
        script_parts.append(f'with title "{title}"')

        if subtitle:
            script_parts.append(f'subtitle "{subtitle}"')

        if self.sound and sound_name:
            script_parts.append(f'sound name "{sound_name}"')
        elif self.sound:
            script_parts.append('sound name "default"')

        script = ' '.join(script_parts)

        result = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            logger.debug(f"Sent macOS notification: {title}")
            return True
        else:
            logger.warning(f"Failed to send macOS notification: {result.stderr}")
            return False

    def _notify_linux(self, title: str, message: str) -> bool:
        """Send notification on Linux using notify-send."""
        result = subprocess.run(
            ['notify-send', title, message],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            logger.debug(f"Sent Linux notification: {title}")
            return True
        else:
            logger.warning(f"notify-send not available or failed: {result.stderr}")
            return False

    def _notify_windows(self, title: str, message: str) -> bool:
        """Send notification on Windows using PowerShell."""
        # Use Windows 10+ toast notifications via PowerShell
        ps_script = f'''
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
        [Windows.UI.Notifications.ToastNotification, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
        [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null

        $template = @"
        <toast>
            <visual>
                <binding template="ToastText02">
                    <text id="1">{title}</text>
                    <text id="2">{message}</text>
                </binding>
            </visual>
        </toast>
"@

        $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
        $xml.LoadXml($template)
        $toast = New-Object Windows.UI.Notifications.ToastNotification $xml
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Multi-Agent Dev").Show($toast)
        '''

        result = subprocess.run(
            ['powershell', '-Command', ps_script],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            logger.debug(f"Sent Windows notification: {title}")
            return True
        else:
            logger.warning(f"Failed to send Windows notification: {result.stderr}")
            return False

    def notify_stage_started(self, stage: str) -> bool:
        """Notify that a pipeline stage has started."""
        return self.notify(
            title="Multi-Agent Pipeline",
            message=f"Started: {stage}",
            subtitle="Stage Started",
            sound_name="Hero"
        )

    def notify_stage_completed(self, stage: str, duration: Optional[float] = None) -> bool:
        """Notify that a pipeline stage has completed."""
        message = f"Completed: {stage}"
        if duration:
            message += f" ({duration:.1f}s)"

        return self.notify(
            title="Multi-Agent Pipeline ✓",
            message=message,
            subtitle="Stage Completed",
            sound_name="Glass"
        )

    def notify_stage_failed(self, stage: str, error: str) -> bool:
        """Notify that a pipeline stage has failed."""
        return self.notify(
            title="Multi-Agent Pipeline ✗",
            message=f"Failed: {stage}\nError: {error[:50]}",
            subtitle="Stage Failed",
            sound_name="Basso"
        )

    def notify_human_review_needed(self) -> bool:
        """Notify that human review is needed."""
        return self.notify(
            title="Multi-Agent Pipeline - Action Required",
            message="Human review needed. Please check workspace/human_review.json",
            subtitle="Awaiting Your Decision",
            sound_name="Ping"
        )

    def notify_pipeline_completed(self, selected_approach: int) -> bool:
        """Notify that entire pipeline has completed."""
        return self.notify(
            title="Multi-Agent Pipeline Complete! 🎉",
            message=f"Successfully integrated approach #{selected_approach}",
            subtitle="All Done",
            sound_name="Glass"
        )

    def notify_pipeline_failed(self, error: str) -> bool:
        """Notify that pipeline has failed."""
        return self.notify(
            title="Multi-Agent Pipeline Failed",
            message=f"Error: {error[:100]}",
            subtitle="Pipeline Stopped",
            sound_name="Sosumi"
        )

    def notify_permission_needed(self, tool_name: str, tool_argument: str) -> bool:
        """도구 실행 권한 승인이 필요할 때 알림.

        Args:
            tool_name: 도구 이름 (e.g., "Bash")
            tool_argument: 도구 인자 (e.g., "npm install")

        Returns:
            True if notification was sent
        """
        return self.notify(
            title="Multi-Agent Pipeline - 권한 승인 필요",
            message=f"{tool_name}: {tool_argument[:80]}",
            subtitle="permission-decision.json에 응답해주세요",
            sound_name="Ping"
        )
