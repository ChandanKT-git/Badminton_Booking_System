from datetime import datetime, time, timedelta
from django.db.models import Q, Sum
from booking.models import Court, Equipment, Coach, CoachAvailability, Booking, BookingEquipment


class AvailabilityService:
    """Service for checking resource availability"""
    
    @staticmethod
    def get_available_courts(date, start_time, end_time):
        """Get all courts available for the given time slot"""
        # Get all active courts
        all_courts = Court.objects.filter(is_active=True)
        
        # Get courts that are already booked in this time slot
        booked_court_ids = Booking.objects.filter(
            date=date,
            start_time__lt=end_time,
            end_time__gt=start_time,
            status='CONFIRMED'
        ).values_list('court_id', flat=True)
        
        # Return courts that are not booked
        return all_courts.exclude(id__in=booked_court_ids)
    
    @staticmethod
    def get_available_equipment(date, start_time, end_time, equipment_type=None):
        """Get equipment with available quantities for the given time slot"""
        equipment_qs = Equipment.objects.all()
        
        if equipment_type:
            equipment_qs = equipment_qs.filter(equipment_type=equipment_type)
        
        available_equipment = []
        for equipment in equipment_qs:
            available_qty = equipment.get_available_quantity(date, start_time, end_time)
            if available_qty > 0:
                available_equipment.append({
                    'equipment': equipment,
                    'available_quantity': available_qty
                })
        
        return available_equipment
    
    @staticmethod
    def get_available_coaches(date, start_time, end_time):
        """Get coaches available for the given time slot"""
        # Get day of week (0=Monday, 6=Sunday)
        day_of_week = date.weekday()
        
        # Get coaches who have availability on this day and time
        available_coach_ids = CoachAvailability.objects.filter(
            day_of_week=day_of_week,
            start_time__lte=start_time,
            end_time__gte=end_time,
            coach__is_active=True
        ).values_list('coach_id', flat=True)
        
        # Get coaches who are already booked in this time slot
        booked_coach_ids = Booking.objects.filter(
            date=date,
            start_time__lt=end_time,
            end_time__gt=start_time,
            status='CONFIRMED',
            coach__isnull=False
        ).values_list('coach_id', flat=True)
        
        # Return coaches that are available but not booked
        return Coach.objects.filter(
            id__in=available_coach_ids
        ).exclude(id__in=booked_coach_ids)
    
    @staticmethod
    def check_court_available(court_id, date, start_time, end_time, exclude_booking_id=None):
        """Check if a specific court is available"""
        query = Booking.objects.filter(
            court_id=court_id,
            date=date,
            start_time__lt=end_time,
            end_time__gt=start_time,
            status='CONFIRMED'
        )
        
        if exclude_booking_id:
            query = query.exclude(id=exclude_booking_id)
        
        return not query.exists()
    
    @staticmethod
    def check_coach_available(coach_id, date, start_time, end_time, exclude_booking_id=None):
        """Check if a specific coach is available"""
        # First check if coach has availability on this day/time
        day_of_week = date.weekday()
        has_availability = CoachAvailability.objects.filter(
            coach_id=coach_id,
            day_of_week=day_of_week,
            start_time__lte=start_time,
            end_time__gte=end_time
        ).exists()
        
        if not has_availability:
            return False
        
        # Then check if coach is not already booked
        query = Booking.objects.filter(
            coach_id=coach_id,
            date=date,
            start_time__lt=end_time,
            end_time__gt=start_time,
            status='CONFIRMED'
        )
        
        if exclude_booking_id:
            query = query.exclude(id=exclude_booking_id)
        
        return not query.exists()
    
    @staticmethod
    def check_equipment_available(equipment_id, quantity, date, start_time, end_time, exclude_booking_id=None):
        """Check if sufficient equipment quantity is available"""
        equipment = Equipment.objects.get(id=equipment_id)
        
        # Calculate booked quantity
        query = BookingEquipment.objects.filter(
            equipment_id=equipment_id,
            booking__date=date,
            booking__start_time__lt=end_time,
            booking__end_time__gt=start_time,
            booking__status='CONFIRMED'
        )
        
        if exclude_booking_id:
            query = query.exclude(booking_id=exclude_booking_id)
        
        booked_quantity = query.aggregate(total=Sum('quantity'))['total'] or 0
        available_quantity = equipment.total_quantity - booked_quantity
        
        return available_quantity >= quantity
    
    @staticmethod
    def check_all_resources_available(date, start_time, end_time, court_id, equipment_list, coach_id=None):
        """
        Check if all requested resources are available for booking
        
        Args:
            date: Booking date
            start_time: Start time
            end_time: End time
            court_id: Court ID
            equipment_list: List of dicts with 'equipment_id' and 'quantity'
            coach_id: Optional coach ID
        
        Returns:
            dict with 'available' (bool) and 'errors' (list)
        """
        errors = []
        
        # Check court
        if not AvailabilityService.check_court_available(court_id, date, start_time, end_time):
            errors.append("Selected court is not available for this time slot")
        
        # Check equipment
        for item in equipment_list:
            if not AvailabilityService.check_equipment_available(
                item['equipment_id'], 
                item['quantity'], 
                date, 
                start_time, 
                end_time
            ):
                equipment = Equipment.objects.get(id=item['equipment_id'])
                errors.append(f"Insufficient {equipment.name} available")
        
        # Check coach
        if coach_id:
            if not AvailabilityService.check_coach_available(coach_id, date, start_time, end_time):
                errors.append("Selected coach is not available for this time slot")
        
        return {
            'available': len(errors) == 0,
            'errors': errors
        }
    
    @staticmethod
    def get_time_slots(date, slot_duration_minutes=60):
        """
        Generate available time slots for a given date
        
        Args:
            date: Date to generate slots for
            slot_duration_minutes: Duration of each slot in minutes
        
        Returns:
            List of dicts with 'start_time', 'end_time', 'display'
        """
        slots = []
        start_hour = 6  # 6 AM
        end_hour = 22   # 10 PM
        
        current_time = time(start_hour, 0)
        end_time_limit = time(end_hour, 0)
        
        while current_time < end_time_limit:
            # Calculate end time for this slot
            current_datetime = datetime.combine(date, current_time)
            end_datetime = current_datetime + timedelta(minutes=slot_duration_minutes)
            slot_end_time = end_datetime.time()
            
            # Don't create slot if it goes beyond operating hours
            if slot_end_time > end_time_limit:
                break
            
            slots.append({
                'start_time': current_time,
                'end_time': slot_end_time,
                'display': f"{current_time.strftime('%I:%M %p')} - {slot_end_time.strftime('%I:%M %p')}"
            })
            
            # Move to next slot
            current_time = slot_end_time
        
        return slots
