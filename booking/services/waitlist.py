"""
Waitlist service for handling waitlist operations and notifications
"""
from django.utils import timezone
from django.db import transaction
from ..models import Waitlist, Booking


class WaitlistService:
    """Service for managing waitlist functionality"""
    
    @staticmethod
    def add_to_waitlist(user, court, date, start_time, end_time):
        """
        Add a user to the waitlist for a specific slot
        
        Args:
            user: User object
            court: Court object
            date: Booking date
            start_time: Start time
            end_time: End time
            
        Returns:
            Waitlist object or None if already in waitlist
        """
        # Check if user is already in waitlist for this slot
        existing = Waitlist.objects.filter(
            user=user,
            court=court,
            date=date,
            start_time=start_time,
            end_time=end_time,
            status='WAITING'
        ).first()
        
        if existing:
            return None
        
        # Create waitlist entry
        waitlist_entry = Waitlist.objects.create(
            user=user,
            court=court,
            date=date,
            start_time=start_time,
            end_time=end_time,
            status='WAITING'
        )
        
        return waitlist_entry
    
    @staticmethod
    def get_waitlist_position(user, court, date, start_time, end_time):
        """
        Get user's position in the waitlist queue
        
        Returns:
            Position number (1-indexed) or None if not in waitlist
        """
        waitlist_entries = Waitlist.objects.filter(
            court=court,
            date=date,
            start_time=start_time,
            end_time=end_time,
            status='WAITING'
        ).order_by('created_at')
        
        for idx, entry in enumerate(waitlist_entries, start=1):
            if entry.user == user:
                return idx
        
        return None
    
    @staticmethod
    def notify_next_in_queue(court, date, start_time, end_time):
        """
        Notify the next person in the waitlist queue when a slot becomes available
        
        Args:
            court: Court object
            date: Booking date
            start_time: Start time
            end_time: End time
            
        Returns:
            Waitlist entry that was notified, or None if queue is empty
        """
        with transaction.atomic():
            # Get the next person in queue (FIFO)
            next_in_queue = Waitlist.objects.filter(
                court=court,
                date=date,
                start_time=start_time,
                end_time=end_time,
                status='WAITING'
            ).select_for_update().order_by('created_at').first()
            
            if next_in_queue:
                # Mark as notified
                next_in_queue.status = 'NOTIFIED'
                next_in_queue.notified_at = timezone.now()
                next_in_queue.save()
                
                # In a real application, send email/SMS notification here
                # For now, we'll just log it
                print(f"NOTIFICATION: {next_in_queue.user.username} - Slot available for {court.name} on {date} ({start_time}-{end_time})")
                
                return next_in_queue
        
        return None
    
    @staticmethod
    def expire_old_notifications():
        """
        Expire notifications that are older than 24 hours
        This should be run periodically (e.g., via cron job)
        """
        from datetime import timedelta
        
        expiry_time = timezone.now() - timedelta(hours=24)
        
        expired_count = Waitlist.objects.filter(
            status='NOTIFIED',
            notified_at__lt=expiry_time
        ).update(status='EXPIRED')
        
        return expired_count
    
    @staticmethod
    def get_user_waitlist_entries(user):
        """
        Get all active waitlist entries for a user
        
        Returns:
            QuerySet of Waitlist objects
        """
        return Waitlist.objects.filter(
            user=user,
            status__in=['WAITING', 'NOTIFIED']
        ).select_related('court').order_by('created_at')
    
    @staticmethod
    def remove_from_waitlist(waitlist_id, user):
        """
        Remove a user from the waitlist
        
        Args:
            waitlist_id: ID of the waitlist entry
            user: User object (for verification)
            
        Returns:
            True if removed, False otherwise
        """
        try:
            waitlist_entry = Waitlist.objects.get(id=waitlist_id, user=user)
            waitlist_entry.delete()
            return True
        except Waitlist.DoesNotExist:
            return False
