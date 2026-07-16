from celery_app import celery_app
from helpers.config import get_settings
from time import sleep
import logging
from datetime import datetime
import asyncio

logger = logging.getLogger("celery.task")

@celery_app.task(bind=True, name="tasks.mail_service.send_email")
def send_email(self,mail_wait_seonds: int):
    asyncio.run(_send_email(self, mail_wait_seonds))


async def _send_email(task_instance, mail_wait_seonds: int):
     
     start_time = str(datetime.now())
     task_instance.update_state(state='PROGRESS', 
                                meta={'status': 'Sending email...',
                                       'start_time': start_time})
     logger.info(f"Simulating email sending for {mail_wait_seonds} seconds...")
     for ix in range(15):
        logger.info(f"Sending report {ix}...")
        await asyncio.sleep(3)  # Simulate time taken to send a report

        return {"message": "Reports sent successfully!",
                "success": True,
                "end_time": str(datetime.now())}


