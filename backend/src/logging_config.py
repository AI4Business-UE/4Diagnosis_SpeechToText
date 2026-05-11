import logging

logger = logging.getLogger('all_loggs')
logger.setLevel(logging.DEBUG) 

if not logger.handlers:
    file_handler = logging.FileHandler('all_loggs.log', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
