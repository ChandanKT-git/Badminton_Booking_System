from django.contrib import admin
from .models import Court, Equipment, Coach, CoachAvailability, PricingRule, Booking, BookingEquipment, Waitlist


@admin.register(Court)
class CourtAdmin(admin.ModelAdmin):
    list_display = ['name', 'court_type', 'is_active']
    list_filter = ['court_type', 'is_active']
    search_fields = ['name']


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'equipment_type', 'total_quantity']
    list_filter = ['equipment_type']
    search_fields = ['name']


class CoachAvailabilityInline(admin.TabularInline):
    model = CoachAvailability
    extra = 1


@admin.register(Coach)
class CoachAdmin(admin.ModelAdmin):
    list_display = ['name', 'hourly_fee', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name']
    inlines = [CoachAvailabilityInline]


@admin.register(PricingRule)
class PricingRuleAdmin(admin.ModelAdmin):
    list_display = ['name', 'rule_type', 'is_enabled', 'priority', 'multiplier', 'flat_fee']
    list_filter = ['rule_type', 'is_enabled']
    list_editable = ['is_enabled', 'priority']
    search_fields = ['name']
    ordering = ['priority', 'name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'rule_type', 'is_enabled', 'priority')
        }),
        ('Pricing Configuration', {
            'fields': ('is_percentage', 'multiplier', 'flat_fee')
        }),
        ('Conditions', {
            'fields': ('start_time', 'end_time', 'applies_to_days'),
            'description': 'Configure when this rule applies'
        }),
    )


class BookingEquipmentInline(admin.TabularInline):
    model = BookingEquipment
    extra = 0
    readonly_fields = ['equipment', 'quantity']


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'court', 'date', 'start_time', 'end_time', 'coach', 'total_price', 'status', 'created_at']
    list_filter = ['status', 'date', 'court', 'coach']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['user', 'court', 'date', 'start_time', 'end_time', 'coach', 
                       'base_price', 'total_price', 'price_breakdown', 'created_at', 'updated_at']
    inlines = [BookingEquipmentInline]
    date_hierarchy = 'date'
    
    fieldsets = (
        ('Booking Details', {
            'fields': ('user', 'court', 'date', 'start_time', 'end_time', 'coach')
        }),
        ('Pricing', {
            'fields': ('base_price', 'total_price', 'price_breakdown')
        }),
        ('Status', {
            'fields': ('status', 'created_at', 'updated_at')
        }),
    )
    
    def has_add_permission(self, request):
        # Bookings should be created through the frontend
        return False


@admin.register(Waitlist)
class WaitlistAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'court', 'date', 'start_time', 'end_time', 'status', 'created_at', 'notified_at']
    list_filter = ['status', 'date', 'court']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['user', 'court', 'date', 'start_time', 'end_time', 'created_at', 'notified_at']
    date_hierarchy = 'date'
    
    fieldsets = (
        ('Waitlist Details', {
            'fields': ('user', 'court', 'date', 'start_time', 'end_time')
        }),
        ('Status', {
            'fields': ('status', 'created_at', 'notified_at')
        }),
    )

