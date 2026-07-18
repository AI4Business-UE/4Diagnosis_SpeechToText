from django.apps import AppConfig


class AppSttConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app_stt'

    def ready(self): 
        import logging
        from app_stt.pipeline import get_pipeline
        logger = logging.getLogger(__name__)
        
        logger.info("Initializing ML Pipeline into memory...")
        get_pipeline()
        logger.info("ML Pipeline ready.")