import logging
import json

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "name": record.name,
        }
        if hasattr(record, 'conversation_id'):
            log_record['conversation_id'] = record.conversation_id
        if hasattr(record, 'client_id'):
            log_record['client_id'] = record.client_id
        return json.dumps(log_record, default=str)

def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Remove any existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Stream Handler
    stream_handler = logging.StreamHandler()
    formatter = JsonFormatter()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    # File Handler
    file_handler = logging.FileHandler('chatbot.log')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)