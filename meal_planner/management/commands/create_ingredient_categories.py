"""
Management command to create default ingredient categories for shopping lists.
"""

from django.core.management.base import BaseCommand
from recipe_hub.models import IngredientCategory


class Command(BaseCommand):
    help = 'Creates default ingredient categories for shopping lists'

    def handle(self, *args, **options):
        """Create default ingredient categories with keywords for auto-categorization."""
        
        categories = [
            {
                'name': 'Produce',
                'display_order': 1,
                'keywords': 'lettuce,tomato,onion,garlic,potato,carrot,celery,pepper,cucumber,spinach,kale,broccoli,cauliflower,zucchini,mushroom,corn,peas,beans,apple,banana,orange,lemon,lime,berry,strawberry,grape,melon,avocado,eggplant,radish,asparagus,pineapple,peach,pear,plum,cherry,apricot,mango,watermelon,cabbage,green beans,pumpkin,sweet potato'
            },
            {
                'name': 'Meat & Seafood',
                'display_order': 2,
                'keywords': 'chicken,beef,pork,lamb,turkey,duck,veal,fish,salmon,tuna,shrimp,crab,lobster,bacon,sausage,ham,steak,ground beef,mince,clams,oysters,mussels,squid,scallops,trout,tilapia,mackerel'
            },
            {
                'name': 'Dairy & Eggs',
                'display_order': 3,
                'keywords': 'milk,cheese,yogurt,butter,cream,egg,cottage cheese,sour cream,cream cheese,mozzarella,cheddar,parmesan,feta,ghee,goat cheese,ricotta,ice cream,half-and-half,egg whites'
            },
            {
                'name': 'Bakery & Bread',
                'display_order': 4,
                'keywords': 'bread,roll,bagel,muffin,croissant,tortilla,pita,naan,baguette,ciabatta,brioche,english muffin,cake,pastries,pizza dough'
            },
            {
                'name': 'Pantry Staples',
                'display_order': 5,
                'keywords': 'rice,pasta,noodles,flour,sugar,salt,pepper,oil,vinegar,sauce,ketchup,mustard,mayo,honey,syrup,cereal,oats,quinoa,couscous,lentils,chickpeas,beans,tomato sauce,coconut milk,broth,bouillon,baking powder,baking soda,yeast,cocoa powder,nut butter,jam,jelly,pickles,olives,salad dressing,soy sauce,worcestershire sauce,hot sauce'
            },
            {
                'name': 'Herbs & Spices',
                'display_order': 6,
                'keywords': 'basil,oregano,thyme,rosemary,sage,parsley,cilantro,dill,mint,cumin,paprika,cinnamon,nutmeg,ginger,turmeric,curry,chili,cayenne,bay leaf,clove,cardamom,vanilla,allspice,saffron,peppercorns'
            },
            {
                'name': 'Frozen Foods',
                'display_order': 7,
                'keywords': 'frozen,ice cream,frozen vegetables,frozen fruit,frozen pizza,frozen meals,frozen desserts,frozen waffles,frozen seafood,frozen chicken,frozen fries,frozen dough'
            },
            {
                'name': 'Beverages',
                'display_order': 8,
                'keywords': 'water,juice,soda,coffee,tea,wine,beer,milk,almond milk,soy milk,coconut water,sparkling water,energy drink,smoothie,iced tea,kombucha,cocoa'
            },
            {
                'name': 'Snacks & Sweets',
                'display_order': 9,
                'keywords': 'chips,crackers,cookies,chocolate,candy,nuts,popcorn,pretzels,granola,trail mix,dried fruit,protein bar,gum,fruit snacks,ice cream bars'
            },
            {
                'name': 'Household & Cleaning',
                'display_order': 10,
                'keywords': 'detergent,soap,paper towels,toilet paper,trash bags,cleaner,disinfectant,wipes,foil,plastic wrap,dish soap,sponges,batteries,light bulbs,air freshener,laundry supplies'
            },
            {
                'name': 'Health & Personal Care',
                'display_order': 11,
                'keywords': 'shampoo,conditioner,body wash,toothpaste,toothbrush,deodorant,lotion,medicine,vitamins,supplements,razors,shaving cream,sunscreen,hair products,facial care,first aid'
            },
            {
                'name': 'Pet Supplies',
                'display_order': 12,
                'keywords': 'pet food,cat litter,pet treats,pet toys,pet accessories'
            },
            {
                'name': 'Baby & Child Care',
                'display_order': 13,
                'keywords': 'diapers,baby wipes,baby food,formula,baby lotion,baby shampoo,pacifiers,baby snacks'
            },
            {
                'name': 'Other',
                'display_order': 14,
                'keywords': ''
            }
        ]
        
        created_count = 0
        updated_count = 0
        
        for cat_data in categories:
            category, created = IngredientCategory.objects.get_or_create(
                name=cat_data['name'],
                defaults={
                    'display_order': cat_data['display_order'],
                    'keywords': cat_data['keywords'],
                    'is_active': True
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created category: {category.name}')
                )
            else:
                # Update existing category
                category.display_order = cat_data['display_order']
                category.keywords = cat_data['keywords']
                category.save()
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'Updated category: {category.name}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nTotal: {created_count} categories created, '
                f'{updated_count} categories updated.'
            )
        )