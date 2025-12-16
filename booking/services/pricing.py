from decimal import Decimal
from datetime import datetime
from booking.models import PricingRule, Court, Coach, Equipment


class PricingEngine:
    """Service for calculating dynamic pricing based on configurable rules"""
    
    BASE_COURT_PRICE = Decimal('500.00')  # Base price per hour slot
    
    @staticmethod
    def calculate_price(court, date, start_time, end_time, equipment_list=None, coach=None):
        """
        Calculate total price with breakdown based on enabled pricing rules
        
        Args:
            court: Court instance
            date: Booking date
            start_time: Start time
            end_time: End time
            equipment_list: List of Equipment instances (optional)
            coach: Coach instance (optional)
        
        Returns:
            dict with 'total_price', 'base_price', 'breakdown' (list of applied rules)
        """
        if equipment_list is None:
            equipment_list = []
        
        # Start with base price
        current_price = PricingEngine.BASE_COURT_PRICE
        breakdown = [{
            'rule': 'Base Court Price',
            'type': 'base',
            'amount': float(current_price)
        }]
        
        # Get all enabled pricing rules ordered by priority
        pricing_rules = PricingRule.objects.filter(is_enabled=True).order_by('priority')
        
        day_of_week = date.weekday()
        
        for rule in pricing_rules:
            applied = False
            rule_amount = Decimal('0.00')
            
            # Check if rule applies based on type
            if rule.rule_type == 'PEAK_HOURS':
                # Check if booking time overlaps with peak hours
                if rule.start_time and rule.end_time:
                    if PricingEngine._time_overlaps(start_time, end_time, rule.start_time, rule.end_time):
                        applied = True
            
            elif rule.rule_type == 'WEEKEND':
                # Check if booking is on specified days
                if rule.applies_to_days:
                    applicable_days = [int(d.strip()) for d in rule.applies_to_days.split(',') if d.strip()]
                    if day_of_week in applicable_days:
                        applied = True
            
            elif rule.rule_type == 'INDOOR_PREMIUM':
                # Check if court is indoor
                if court.court_type == 'INDOOR':
                    applied = True
            
            elif rule.rule_type == 'EQUIPMENT_FEE':
                # Apply for each equipment item
                if equipment_list:
                    applied = True
            
            elif rule.rule_type == 'COACH_FEE':
                # Apply if coach is selected
                if coach:
                    applied = True
            
            # Apply the rule if conditions are met
            if applied:
                if rule.is_percentage:
                    # Apply multiplier to current price
                    additional_amount = current_price * (rule.multiplier - Decimal('1.0'))
                    rule_amount = additional_amount
                    current_price += additional_amount
                else:
                    # Add flat fee
                    if rule.rule_type == 'EQUIPMENT_FEE':
                        # Apply flat fee per equipment item
                        total_equipment_fee = rule.flat_fee * len(equipment_list)
                        rule_amount = total_equipment_fee
                        current_price += total_equipment_fee
                    elif rule.rule_type == 'COACH_FEE':
                        # Use coach's hourly fee
                        rule_amount = coach.hourly_fee
                        current_price += coach.hourly_fee
                    else:
                        rule_amount = rule.flat_fee
                        current_price += rule.flat_fee
                
                breakdown.append({
                    'rule': rule.name,
                    'type': rule.rule_type,
                    'amount': float(rule_amount),
                    'is_percentage': rule.is_percentage,
                    'multiplier': float(rule.multiplier) if rule.is_percentage else None
                })
        
        return {
            'total_price': current_price,
            'base_price': PricingEngine.BASE_COURT_PRICE,
            'breakdown': breakdown
        }
    
    @staticmethod
    def _time_overlaps(start1, end1, start2, end2):
        """Check if two time ranges overlap"""
        return start1 < end2 and end1 > start2
    
    @staticmethod
    def get_price_preview(court_id, date, start_time, end_time, equipment_ids=None, coach_id=None):
        """
        Get price preview for frontend display
        
        Args:
            court_id: Court ID
            date: Booking date (datetime.date or string)
            start_time: Start time (datetime.time or string)
            end_time: End time (datetime.time or string)
            equipment_ids: List of equipment IDs (optional)
            coach_id: Coach ID (optional)
        
        Returns:
            dict with pricing information
        """
        try:
            court = Court.objects.get(id=court_id)
        except Court.DoesNotExist:
            return {'error': 'Court not found'}
        
        # Parse date if string
        if isinstance(date, str):
            date = datetime.strptime(date, '%Y-%m-%d').date()
        
        # Parse times if strings
        if isinstance(start_time, str):
            start_time = datetime.strptime(start_time, '%H:%M').time()
        if isinstance(end_time, str):
            end_time = datetime.strptime(end_time, '%H:%M').time()
        
        # Get equipment instances
        equipment_list = []
        if equipment_ids:
            equipment_list = list(Equipment.objects.filter(id__in=equipment_ids))
        
        # Get coach instance
        coach = None
        if coach_id:
            try:
                coach = Coach.objects.get(id=coach_id)
            except Coach.DoesNotExist:
                pass
        
        # Calculate price
        pricing_data = PricingEngine.calculate_price(
            court, date, start_time, end_time, equipment_list, coach
        )
        
        return pricing_data
