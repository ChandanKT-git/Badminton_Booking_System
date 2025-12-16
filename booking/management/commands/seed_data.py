from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from booking.models import Court, Equipment, Coach, CoachAvailability, PricingRule
from datetime import time
from decimal import Decimal


class Command(BaseCommand):
    help = 'Seed database with initial data for courts, equipment, coaches, and pricing rules'

    def handle(self, *args, **kwargs):
        self.stdout.write('Seeding database...')
        
        # Create Courts
        self.stdout.write('Creating courts...')
        courts_data = [
            {'name': 'Indoor Court 1', 'court_type': 'INDOOR', 'is_active': True},
            {'name': 'Indoor Court 2', 'court_type': 'INDOOR', 'is_active': True},
            {'name': 'Outdoor Court 1', 'court_type': 'OUTDOOR', 'is_active': True},
            {'name': 'Outdoor Court 2', 'court_type': 'OUTDOOR', 'is_active': True},
        ]
        
        for court_data in courts_data:
            court, created = Court.objects.get_or_create(**court_data)
            if created:
                self.stdout.write(f'  ✓ Created {court.name}')
        
        # Create Equipment
        self.stdout.write('Creating equipment...')
        equipment_data = [
            {'name': 'Premium Racket', 'equipment_type': 'RACKET', 'total_quantity': 10},
            {'name': 'Sports Shoes', 'equipment_type': 'SHOES', 'total_quantity': 8},
        ]
        
        for equip_data in equipment_data:
            equipment, created = Equipment.objects.get_or_create(
                name=equip_data['name'],
                defaults=equip_data
            )
            if created:
                self.stdout.write(f'  ✓ Created {equipment.name}')
        
        # Create Coaches
        self.stdout.write('Creating coaches...')
        
        # Coach A - Mon-Fri 9AM-6PM
        coach_a, created = Coach.objects.get_or_create(
            name='Coach Rajesh Kumar',
            defaults={'hourly_fee': Decimal('200.00'), 'is_active': True}
        )
        if created:
            self.stdout.write(f'  ✓ Created {coach_a.name}')
            # Add availability
            for day in range(0, 5):  # Monday to Friday
                CoachAvailability.objects.create(
                    coach=coach_a,
                    day_of_week=day,
                    start_time=time(9, 0),
                    end_time=time(18, 0)
                )
        
        # Coach B - Mon-Sat 10AM-8PM
        coach_b, created = Coach.objects.get_or_create(
            name='Coach Priya Sharma',
            defaults={'hourly_fee': Decimal('250.00'), 'is_active': True}
        )
        if created:
            self.stdout.write(f'  ✓ Created {coach_b.name}')
            # Add availability
            for day in range(0, 6):  # Monday to Saturday
                CoachAvailability.objects.create(
                    coach=coach_b,
                    day_of_week=day,
                    start_time=time(10, 0),
                    end_time=time(20, 0)
                )
        
        # Coach C - Weekends 8AM-8PM
        coach_c, created = Coach.objects.get_or_create(
            name='Coach Amit Patel',
            defaults={'hourly_fee': Decimal('300.00'), 'is_active': True}
        )
        if created:
            self.stdout.write(f'  ✓ Created {coach_c.name}')
            # Add availability
            for day in [5, 6]:  # Saturday and Sunday
                CoachAvailability.objects.create(
                    coach=coach_c,
                    day_of_week=day,
                    start_time=time(8, 0),
                    end_time=time(20, 0)
                )
        
        # Create Pricing Rules
        self.stdout.write('Creating pricing rules...')
        
        pricing_rules = [
            {
                'name': 'Indoor Court Premium',
                'rule_type': 'INDOOR_PREMIUM',
                'multiplier': Decimal('1.20'),  # 20% increase
                'flat_fee': Decimal('0.00'),
                'is_percentage': True,
                'is_enabled': True,
                'priority': 1,
            },
            {
                'name': 'Peak Hours (6PM-9PM)',
                'rule_type': 'PEAK_HOURS',
                'multiplier': Decimal('1.50'),  # 50% increase
                'flat_fee': Decimal('0.00'),
                'is_percentage': True,
                'is_enabled': True,
                'priority': 2,
                'start_time': time(18, 0),
                'end_time': time(21, 0),
            },
            {
                'name': 'Weekend Premium',
                'rule_type': 'WEEKEND',
                'multiplier': Decimal('1.30'),  # 30% increase
                'flat_fee': Decimal('0.00'),
                'is_percentage': True,
                'is_enabled': True,
                'priority': 3,
                'applies_to_days': '5,6',  # Saturday and Sunday
            },
            {
                'name': 'Racket Rental Fee',
                'rule_type': 'EQUIPMENT_FEE',
                'multiplier': Decimal('1.00'),
                'flat_fee': Decimal('50.00'),
                'is_percentage': False,
                'is_enabled': True,
                'priority': 4,
            },
            {
                'name': 'Shoes Rental Fee',
                'rule_type': 'EQUIPMENT_FEE',
                'multiplier': Decimal('1.00'),
                'flat_fee': Decimal('30.00'),
                'is_percentage': False,
                'is_enabled': True,
                'priority': 5,
            },
            {
                'name': 'Coach Fee',
                'rule_type': 'COACH_FEE',
                'multiplier': Decimal('1.00'),
                'flat_fee': Decimal('0.00'),  # Will use coach's hourly_fee
                'is_percentage': False,
                'is_enabled': True,
                'priority': 6,
            },
        ]
        
        for rule_data in pricing_rules:
            rule, created = PricingRule.objects.get_or_create(
                name=rule_data['name'],
                defaults=rule_data
            )
            if created:
                self.stdout.write(f'  ✓ Created pricing rule: {rule.name}')
        
        # Create admin user if not exists
        self.stdout.write('Creating admin user...')
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser(
                username='admin',
                email='admin@badminton.com',
                password='admin123'
            )
            self.stdout.write('  ✓ Created admin user (username: admin, password: admin123)')
        else:
            self.stdout.write('  ℹ Admin user already exists')
        
        self.stdout.write(self.style.SUCCESS('\n✓ Database seeding completed successfully!'))
        self.stdout.write('\nYou can now:')
        self.stdout.write('  1. Run: python manage.py runserver')
        self.stdout.write('  2. Access admin panel: http://127.0.0.1:8000/admin/')
        self.stdout.write('  3. Login with: admin / admin123')
