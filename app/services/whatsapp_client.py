from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Optional, List
import httpx
from datetime import datetime


logger = logging.getLogger(__name__)


class WhatsAppClient:
    def __init__(self, access_token: str, phone_number_id: str) -> None:
        self.access_token = access_token
        self.phone_number_id = phone_number_id
        self.base_url = "https://graph.facebook.com/v18.0"
        self.client = httpx.AsyncClient(timeout=30.0)

    async def send_text_message(self, to: str, text: str) -> Dict[str, Any]:
        """Send a text message via WhatsApp."""
        url = f"{self.base_url}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": text}
        }
        
        try:
            response = await self.client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to send WhatsApp message: {e}")
            raise

    async def send_template_message(self, to: str, template_name: str, language: str = "en", components: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """Send a template message via WhatsApp."""
        url = f"{self.base_url}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language}
            }
        }
        
        if components:
            payload["template"]["components"] = components
        
        try:
            response = await self.client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to send WhatsApp template: {e}")
            raise

    async def send_interactive_message(self, to: str, header: str, body: str, buttons: List[Dict[str, str]]) -> Dict[str, Any]:
        """Send an interactive message with buttons."""
        url = f"{self.base_url}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        button_components = []
        for i, button in enumerate(buttons[:3]):  # WhatsApp allows max 3 buttons
            button_components.append({
                "type": "button",
                "sub_type": "quick_reply",
                "index": i,
                "parameters": [{"type": "text", "text": button["id"]}]
            })
        
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "header": {"type": "text", "text": header},
                "body": {"text": body},
                "action": {
                    "buttons": button_components
                }
            }
        }
        
        try:
            response = await self.client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to send WhatsApp interactive message: {e}")
            raise

    async def send_calendar_event(self, to: str, event_title: str, event_time: str, event_link: str) -> Dict[str, Any]:
        """Send a calendar event message."""
        body = f"📅 {event_title}\n⏰ {event_time}\n🔗 {event_link}"
        return await self.send_text_message(to, body)

    async def send_help_response(self, to: str, query: str, answer: str, sources: Optional[List[str]] = None) -> Dict[str, Any]:
        """Send a help response with optional sources."""
        body = f"❓ {query}\n\n{answer}"
        if sources:
            body += f"\n\n📚 Sources: {', '.join(sources[:3])}"
        return await self.send_text_message(to, body)

    async def send_quick_actions(self, to: str) -> Dict[str, Any]:
        """Send quick action buttons for common tasks."""
        buttons = [
            {"id": "help", "title": "Get Help"},
            {"id": "schedule", "title": "Schedule Event"},
            {"id": "today", "title": "Today's Schedule"}
        ]
        return await self.send_interactive_message(
            to=to,
            header="🤖 WhatsApp Bot",
            body="What would you like to do?",
            buttons=buttons
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()


class WhatsAppWebhookHandler:
    def __init__(self, whatsapp_client: WhatsAppClient) -> None:
        self.client = whatsapp_client
        self.logger = logging.getLogger(__name__)

    async def handle_message(self, message_data: Dict[str, Any]) -> None:
        """Handle incoming WhatsApp messages."""
        try:
            entry = message_data.get("entry", [{}])[0]
            changes = entry.get("changes", [{}])[0]
            value = changes.get("value", {})
            messages = value.get("messages", [])
            
            for message in messages:
                await self._process_message(message)
                
        except Exception as e:
            self.logger.error(f"Error handling WhatsApp message: {e}")

    async def _process_message(self, message: Dict[str, Any]) -> None:
        """Process individual message."""
        from_number = message.get("from")
        message_type = message.get("type")
        
        if message_type == "text":
            text = message.get("text", {}).get("body", "")
            await self._handle_text_message(from_number, text)
        elif message_type == "interactive":
            await self._handle_interactive_message(from_number, message.get("interactive", {}))

    async def _handle_text_message(self, from_number: str, text: str) -> None:
        """Handle text messages."""
        text_lower = text.lower().strip()
        
        # Quick actions
        if text_lower in ["help", "menu", "start"]:
            await self.client.send_quick_actions(from_number)
        elif "schedule" in text_lower or "event" in text_lower:
            await self.client.send_text_message(
                from_number, 
                "To schedule an event, please provide the details in this format:\n"
                "'Schedule [event name] at [time] for [duration]'\n"
                "Example: 'Schedule team meeting tomorrow 3pm for 1 hour'"
            )
        elif "today" in text_lower or "schedule" in text_lower:
            # This would integrate with your existing calendar functionality
            await self.client.send_text_message(
                from_number,
                "I'll check your calendar for today's events. Please connect your Google account first."
            )
        else:
            # Default help response
            await self.client.send_text_message(
                from_number,
                "Hi! I'm your AI assistant. I can help you with:\n"
                "• Getting help with commands and tools\n"
                "• Scheduling calendar events\n"
                "• Checking your daily schedule\n\n"
                "Type 'help' for quick actions or ask me anything!"
            )

    async def _handle_interactive_message(self, from_number: str, interactive: Dict[str, Any]) -> None:
        """Handle interactive button responses."""
        if interactive.get("type") == "button_reply":
            button_id = interactive.get("button_reply", {}).get("id")
            if button_id == "help":
                await self.client.send_text_message(
                    from_number,
                    "I can help you with:\n"
                    "• Command explanations (e.g., 'help git commit')\n"
                    "• Tool documentation\n"
                    "• Programming questions\n\n"
                    "Just ask me anything!"
                )
            elif button_id == "schedule":
                await self.client.send_text_message(
                    from_number,
                    "To schedule an event, please provide the details in this format:\n"
                    "'Schedule [event name] at [time] for [duration]'"
                )
            elif button_id == "today":
                await self.client.send_text_message(
                    from_number,
                    "I'll check your calendar for today's events. Please connect your Google account first."
                )
