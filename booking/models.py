from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal


class Court(models.Model):
    """Badminton court with indoor/outdoor type"""
    COURT_TYPE_CHOICES = [
        ('INDOOR', 'Indoor'),
        ('OUTDOOR', 'Outdoor'),
    ]
    
    name = models.CharField(max_length=100)
    court_type = models.CharField(max_length=10, choices=COURT_TYPE_CHOICES)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.name} ({self.get_court_type_display()})"
    
    class Meta:
        ordering = ['name']


class Equipment(models.Model):
    """Equipment available for rental"""
    EQUIPMENT_TYPE_CHOICES = [
        ('RACKET', 'Racket'),
        ('SHOES', 'Shoes'),
    ]
    
    name = models.CharField(max_length=100)
    equipment_type = models.CharField(max_length=10, choices=EQUIPMENT_TYPE_CHOICES)
    total_quantity = models.PositiveIntegerField()
    
    def __str__(self):
        return f"{self.name} ({self.get_equipment_type_display()})"
    
    def get_available_quantity(self, date, start_time, end_time):
        """Calculate available quantity for a given time slot"""
        from django.db.models import Sum
        
        # Get all bookings for this equipment in the time slot
        booked_quantity = BookingEquipment.objects.filter(
            equipment=self,
            booking__date=date,
            booking__start_time__lt=end_time,
            booking__end_time__gt=start_time,
            booking__status='CONFIRMED'
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        return self.total_quantity - booked_quantity
    
    class Meta:
        ordering = ['name']


class Coach(models.Model):
    """Coach available for booking"""
    name = models.CharField(max_length=100)
    hourly_fee = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.name} (₹{self.hourly_fee}/hr)"
    
    class Meta:
        ordering = ['name']


class CoachAvailability(models.Model):
    """Weekly availability schedule for coaches"""
    DAY_CHOICES = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ]
    
    coach = models.ForeignKey(Coach, on_delete=models.CASCADE, related_name='availability_slots')
    day_of_week = models.IntegerField(choices=DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    
    def __str__(self):
        return f"{self.coach.name} - {self.get_day_of_week_display()} {self.start_time}-{self.end_time}"
    
    class Meta:
        ordering = ['coach', 'day_of_week', 'start_time']
        verbose_name_plural = 'Coach Availabilities'


class PricingRule(models.Model):
    """Configurable pricing rules for dynamic pricing"""
    RULE_TYPE_CHOICES = [
        ('PEAK_HOURS', 'Peak Hours Premium'),
        ('WEEKEND', 'Weekend Premium'),
        ('INDOOR_PREMIUM', 'Indoor Court Premium'),
        ('EQUIPMENT_FEE', 'Equipment Rental Fee'),
        ('COACH_FEE', 'Coach Fee'),
    ]
    
    name = models.CharField(max_length=200)
    rule_type = models.CharField(max_length=20, choices=RULE_TYPE_CHOICES)
    multiplier = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=1.0,
        help_text="Multiplier for percentage-based rules (e.g., 1.5 for 50% increase)"
    )
    flat_fee = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        help_text="Flat fee to add (for equipment, coach, etc.)"
    )
    is_percentage = models.BooleanField(
        default=True,
        help_text="If true, applies multiplier; if false, adds flat fee"
    )
    is_enabled = models.BooleanField(default=True)
    priority = models.IntegerField(
        default=0,
        help_text="Lower numbers are applied first"
    )
    
    # Time-based conditions
    start_time = models.TimeField(null=True, blank=True, help_text="For peak hours rules")
    end_time = models.TimeField(null=True, blank=True, help_text="For peak hours rules")
    
    # Day-based conditions
    applies_to_days = models.CharField(
        max_length=20, 
        blank=True,
        help_text="Comma-separated day numbers (0=Mon, 6=Sun). E.g., '5,6' for weekends"
    )
    
    def __str__(self):
        return f"{self.name} ({'Enabled' if self.is_enabled else 'Disabled'})"
    
    class Meta:
        ordering = ['priority', 'name']


class Booking(models.Model):
    """Court booking with optional equipment and coach"""
    STATUS_CHOICES = [
        ('CONFIRMED', 'Confirmed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings')
    court = models.ForeignKey(Court, on_delete=models.CASCADE, related_name='bookings')
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    coach = models.ForeignKey(Coach, on_delete=models.SET_NULL, null=True, blank=True, related_name='bookings')
    
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    price_breakdown = models.JSONField(default=dict, help_text="Detailed breakdown of pricing rules applied")
    
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='CONFIRMED')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.court.name} on {self.date} ({self.start_time}-{self.end_time})"
    
    class Meta:
        ordering = ['-date', '-start_time']
        indexes = [
            models.Index(fields=['date', 'start_time', 'end_time']),
            models.Index(fields=['court', 'date']),
        ]


class BookingEquipment(models.Model):
    """Through model for booking equipment with quantities"""
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='equipment_items')
    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    
    def __str__(self):
        return f"{self.booking} - {self.equipment.name} x{self.quantity}"
    
    class Meta:
        unique_together = ['booking', 'equipment']


class Waitlist(models.Model):
    """Waitlist for users when slots are fully booked"""
    STATUS_CHOICES = [
        ('WAITING', 'Waiting'),
        ('NOTIFIED', 'Notified'),
        ('EXPIRED', 'Expired'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='waitlist_entries')
    court = models.ForeignKey(Court, on_delete=models.CASCADE, related_name='waitlist_entries')
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='WAITING')
    created_at = models.DateTimeField(auto_now_add=True)
    notified_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.user.username} - Waitlist for {self.court.name} on {self.date} ({self.start_time}-{self.end_time})"
    
    class Meta:
        ordering = ['created_at']  # FIFO queue
        indexes = [
            models.Index(fields=['court', 'date', 'start_time', 'end_time', 'status']),
        ]
