import logging

logger = logging.getLogger('all_loggs')
logger.setLevel(logging.INFO)

if not logger.handlers:
    # file — full log
    file_handler = logging.FileHandler('all_loggs.log', encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)-8s %(message)s'))
    logger.addHandler(file_handler)

    # console — only warnings and errors
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(logging.Formatter('%(levelname)s %(message)s'))
    logger.addHandler(console_handler)
