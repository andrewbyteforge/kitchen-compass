# Update your 0003_add_crawl_type.py migration file

from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Add crawl type support to CrawlSession model.
    """

    dependencies = [
        ('asda_scraper', '0002_proxyconfiguration_proxyprovidersettings_and_more'),  # Fixed dependency
    ]

    operations = [
        migrations.AddField(
            model_name='crawlsession',
            name='crawl_type',
            field=models.CharField(
                choices=[
                    ('PRODUCT', 'Product Information'),
                    ('NUTRITION', 'Nutritional Information'),
                    ('BOTH', 'Product & Nutrition')
                ],
                default='PRODUCT',
                help_text='Type of information to crawl',
                max_length=20
            ),
        ),
        migrations.AddField(
            model_name='crawlsession',
            name='products_with_nutrition',
            field=models.IntegerField(
                default=0,
                help_text='Number of products with nutritional information found'
            ),
        ),
        migrations.AddField(
            model_name='crawlsession',
            name='nutrition_errors',
            field=models.IntegerField(
                default=0,
                help_text='Number of nutrition crawl errors'
            ),
        ),
    ]