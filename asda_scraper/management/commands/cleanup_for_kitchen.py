from django.core.management.base import BaseCommand
from django.db.models import Q
from asda_scraper.models import AsdaProduct, AsdaCategory

class Command(BaseCommand):
    help = 'One-time cleanup to prepare database for KitchenCompass'
    
    def handle(self, *args, **options):
        # Delete baby products
        baby_filter = (
            Q(category__name__icontains='baby') | 
            Q(category__name__icontains='toddler') |
            Q(category__name__icontains='kids') |
            Q(category__name__icontains='month') |
            Q(name__icontains='baby') |
            Q(name__icontains='toddler') |
            Q(name__icontains='nappy') |
            Q(name__icontains='infant')
        )
        
        count = AsdaProduct.objects.filter(baby_filter).count()
        AsdaProduct.objects.filter(baby_filter).delete()
        self.stdout.write(f'Deleted {count} baby/toddler products')
        
        # Delete non-food products
        non_food_filter = (
            Q(category__name__icontains='household') |
            Q(category__name__icontains='cleaning') |
            Q(category__name__icontains='laundry') |
            Q(category__name__icontains='pet') |
            Q(category__name__icontains='toiletries') |
            Q(category__name__icontains='beauty')
        )
        
        count = AsdaProduct.objects.filter(non_food_filter).count()
        AsdaProduct.objects.filter(non_food_filter).delete()
        self.stdout.write(f'Deleted {count} non-food products')
        
        # Setup categories - deactivate all first
        AsdaCategory.objects.update(is_active=False)
        
        # Activate only food categories
        food_categories = {
            '1215686352935': 'Fruit, Veg & Flowers',
            '1215135760597': 'Meat, Poultry & Fish',
            '1215686354843': 'Bakery',
            '1215660378320': 'Chilled Food',
            '1215338621416': 'Frozen Food',
            '1215337189632': 'Food Cupboard',
            '1215686356579': 'Sweets, Treats & Snacks',
            '1215686355606': 'Dietary & Lifestyle',
            '1215135760614': 'Drinks',
            '1215685911554': 'Beer, Wine & Spirits',
            '1215686351451': 'World Food'
        }
        
        for url_code, name in food_categories.items():
            AsdaCategory.objects.update_or_create(
                url_code=url_code,
                defaults={'name': name, 'is_active': True}
            )
        
        self.stdout.write(self.style.SUCCESS(
            f'\nDatabase cleaned! '
            f'Active categories: {AsdaCategory.objects.filter(is_active=True).count()}, '
            f'Total products: {AsdaProduct.objects.count()}'
        ))