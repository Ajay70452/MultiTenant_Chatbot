import httpx
import logging
from sqlalchemy.orm import Session
from src.core.db import get_db
from src.models.models import Client
import datetime

logger = logging.getLogger(__name__)

async def route_via_webhook(client_id: str, conversation_id: str, lead_details: dict):
    db: Session = next(get_db())
    try:
        logger.info(f"route_via_webhook called with lead_details: {lead_details}", extra={'client_id': client_id, 'conversation_id': conversation_id})
        
        client = db.query(Client).filter(Client.client_id == client_id).first()
        if not client or not client.lead_webhook_url:
            logger.warning(
                f"Webhook URL not found for client {client_id}. Skipping webhook.",
                extra={'client_id': client_id, 'conversation_id': conversation_id}
            )
            return

        payload = {
            "client_id": client_id,
            "conversation_id": conversation_id,
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "name": lead_details.get("name"),
            "phone": lead_details.get("phone"),
            "email": lead_details.get("email"),
            "lead_data": lead_details
        }

        logger.info(f"Sending lead to webhook: {client.lead_webhook_url}", extra={'client_id': client_id, 'conversation_id': conversation_id})
        logger.debug(f"Webhook payload: {payload}", extra={'client_id': client_id, 'conversation_id': conversation_id})

        try:
            async with httpx.AsyncClient() as client_post:
                response = await client_post.post(client.lead_webhook_url, json=payload, timeout=10.0)

                if response.status_code == 200:
                    logger.info(
                        f"Successfully sent lead to webhook for client {client_id}.",
                        extra={'client_id': client_id, 'conversation_id': conversation_id}
                    )
                else:
                    logger.error(
                        f"Failed to send lead to webhook for client {client_id}. Status: {response.status_code}, Response: {response.text}",
                        extra={'client_id': client_id, 'conversation_id': conversation_id}
                    )
        except httpx.RequestError as e:
            logger.error(
                f"Error sending lead to webhook for client {client_id}: {e}",
                extra={'client_id': client_id, 'conversation_id': conversation_id}
            )

    except Exception as e:
        logger.error(
            f"Error routing webhook for client {client_id}: {e}",
            extra={'client_id': client_id, 'conversation_id': conversation_id}
        )
    finally:
        db.close()