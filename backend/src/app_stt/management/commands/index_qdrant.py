from django.core.management.base import BaseCommand, CommandError
from app_stt.pipeline.stages.rag.qdrant import index_database
from app_stt.pipeline import PipelineConfig


class Command(BaseCommand):
    help = "Indexes Qdrant vector database with macro description templates"
     
    
    def handle(self, *args, **options):
        cfg = PipelineConfig()
        self.stdout.write(
            self.style.NOTICE(f'COMMAND: Indexing Qdrant database in client mode `{cfg.qdrant_client_mode.name}`...'))
        
        index_database(cfg)
        
        self.stdout.write(
            self.style.SUCCESS(f'COMMAND: Qdrant database indexed successfully!')
        )