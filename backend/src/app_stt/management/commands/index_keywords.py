from django.core.management.base import BaseCommand

from app_stt.models import Keyword
from app_stt.data.medical_keywords import MEDICAL_KEYWORDS


class Command(BaseCommand):
    help = "Indexes keywords for GPT-Transcribe model."
    
    
    def handle(self, *args, **kwargs):
        self.stdout.write(
            self.style.NOTICE(f'COMMAND: Indexing keywords...')
        )
        
        keywords_to_insert = [] 
        for keyword in MEDICAL_KEYWORDS:
            k = Keyword(text=keyword)
            k.full_clean()
            keywords_to_insert.append(k)
            
        Keyword.objects.bulk_create(keywords_to_insert)
        
        self.stdout.write(
            self.style.SUCCESS(f'COMMAND: Keywords successfully indexed!')
        )