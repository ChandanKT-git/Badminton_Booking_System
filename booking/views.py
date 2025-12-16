from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.http import JsonResponse
from django.db import transaction
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from datetime import datetime, timedelta, date
from decimal import Decimal

from .models import Court, Equipment, Coach, Booking, BookingEquipment, Waitlist
from .services.availability import AvailabilityService
from .services.pricing import PricingEngine
from .services.waitlist import WaitlistService


def home(request):
    """Home page with date picker"""
    return render(request, 'booking/home.html')


def register_view(request):
    """User registration"""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Account created successfully!')
            return redirect('home')
    else:
        form = UserCreationForm()
    return render(request, 'booking/register.html', {'form': form})


def login_view(request):
    """User login"""
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Welcome back, {user.username}!')
            return redirect('home')
    else:
        form = AuthenticationForm()
    return render(request, 'booking/login.html', {'form': form})


def logout_view(request):
    """User logout"""
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('home')


@login_required
def booking_page(request):
    """Main booking page with slot selection"""
    # Get date from query params or default to today
    selected_date_str = request.GET.get('date', date.today().isoformat())
    try:
        selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
    except ValueError:
        selected_date = date.today()
    
    # Generate next 7 days for date selection
    available_dates = [date.today() + timedelta(days=i) for i in range(7)]
    
    # Get time slots
    time_slots = AvailabilityService.get_time_slots(selected_date)
    
    # Get all courts, equipment, and coaches for display
    courts = Court.objects.filter(is_active=True)
    equipment = Equipment.objects.all()
    coaches = Coach.objects.filter(is_active=True)
    
    context = {
        'selected_date': selected_date,
        'available_dates': available_dates,
        'time_slots': time_slots,
        'courts': courts,
        'equipment': equipment,
        'coaches': coaches,
    }
    
    return render(request, 'booking/booking.html', context)


@require_http_methods(["GET"])
def api_check_availability(request):
    """API endpoint to check resource availability"""
    try:
        date_str = request.GET.get('date')
        start_time_str = request.GET.get('start_time')
        end_time_str = request.GET.get('end_time')
        
        booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        start_time = datetime.strptime(start_time_str, '%H:%M').time()
        end_time = datetime.strptime(end_time_str, '%H:%M').time()
        
        # Get available resources
        available_courts = AvailabilityService.get_available_courts(booking_date, start_time, end_time)
        available_equipment = AvailabilityService.get_available_equipment(booking_date, start_time, end_time)
        available_coaches = AvailabilityService.get_available_coaches(booking_date, start_time, end_time)
        
        return JsonResponse({
            'success': True,
            'courts': [{'id': c.id, 'name': c.name, 'type': c.court_type} for c in available_courts],
            'equipment': [{'id': e['equipment'].id, 'name': e['equipment'].name, 'available_qty': e['available_quantity']} for e in available_equipment],
            'coaches': [{'id': c.id, 'name': c.name, 'fee': str(c.hourly_fee)} for c in available_coaches],
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@require_http_methods(["POST"])
def api_calculate_price(request):
    """API endpoint to calculate price dynamically"""
    try:
        import json
        data = json.loads(request.body)
        
        court_id = data.get('court_id')
        date_str = data.get('date')
        start_time_str = data.get('start_time')
        end_time_str = data.get('end_time')
        equipment_ids = data.get('equipment_ids', [])
        coach_id = data.get('coach_id')
        
        pricing_data = PricingEngine.get_price_preview(
            court_id, date_str, start_time_str, end_time_str, equipment_ids, coach_id
        )
        
        if 'error' in pricing_data:
            return JsonResponse({'success': False, 'error': pricing_data['error']}, status=400)
        
        return JsonResponse({
            'success': True,
            'base_price': str(pricing_data['base_price']),
            'total_price': str(pricing_data['total_price']),
            'breakdown': pricing_data['breakdown']
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
def confirm_booking(request):
    """Create a new booking with atomic transaction and concurrent booking prevention"""
    try:
        import json
        data = json.loads(request.body)
        
        court_id = data.get('court_id')
        date_str = data.get('date')
        start_time_str = data.get('start_time')
        end_time_str = data.get('end_time')
        equipment_list = data.get('equipment', [])  # List of {'id': ..., 'quantity': ...}
        coach_id = data.get('coach_id')
        
        # Parse date and times
        booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        start_time = datetime.strptime(start_time_str, '%H:%M').time()
        end_time = datetime.strptime(end_time_str, '%H:%M').time()
        
        # Prepare equipment list for availability check
        equipment_check_list = [{'equipment_id': e['id'], 'quantity': e['quantity']} for e in equipment_list]
        
        # Use atomic transaction with SELECT FOR UPDATE to prevent concurrent bookings
        with transaction.atomic():
            # Lock the court row to prevent concurrent bookings
            court = Court.objects.select_for_update().get(id=court_id)
            
            # Check if court is already booked for this slot (with lock held)
            existing_booking = Booking.objects.select_for_update().filter(
                court=court,
                date=booking_date,
                start_time__lt=end_time,
                end_time__gt=start_time,
                status='CONFIRMED'
            ).first()
            
            if existing_booking:
                # Slot is already booked, offer waitlist
                return JsonResponse({
                    'success': False,
                    'slot_full': True,
                    'message': 'This slot is already booked. Would you like to join the waitlist?'
                }, status=409)
            
            # Check availability of all resources
            availability_check = AvailabilityService.check_all_resources_available(
                booking_date, start_time, end_time, court_id, equipment_check_list, coach_id
            )
            
            if not availability_check['available']:
                return JsonResponse({
                    'success': False,
                    'errors': availability_check['errors']
                }, status=400)
            
            # Get resources
            coach = Coach.objects.get(id=coach_id) if coach_id else None
            equipment_instances = [Equipment.objects.get(id=e['id']) for e in equipment_list]
            
            # Calculate pricing
            pricing_data = PricingEngine.calculate_price(
                court, booking_date, start_time, end_time, equipment_instances, coach
            )
            
            # Create booking
            booking = Booking.objects.create(
                user=request.user,
                court=court,
                date=booking_date,
                start_time=start_time,
                end_time=end_time,
                coach=coach,
                base_price=pricing_data['base_price'],
                total_price=pricing_data['total_price'],
                price_breakdown=pricing_data['breakdown'],
                status='CONFIRMED'
            )
            
            # Add equipment
            for equip_data in equipment_list:
                BookingEquipment.objects.create(
                    booking=booking,
                    equipment_id=equip_data['id'],
                    quantity=equip_data['quantity']
                )
            
            return JsonResponse({
                'success': True,
                'booking_id': booking.id,
                'message': 'Booking confirmed successfully!'
            })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)



@login_required
def booking_history(request):
    """View user's booking history and waitlist entries"""
    bookings = Booking.objects.filter(user=request.user).select_related('court', 'coach').prefetch_related('equipment_items__equipment')
    waitlist_entries = WaitlistService.get_user_waitlist_entries(request.user)
    
    return render(request, 'booking/booking_history.html', {
        'bookings': bookings,
        'waitlist_entries': waitlist_entries
    })


@login_required
@require_http_methods(["POST"])
def join_waitlist(request):
    """Add user to waitlist for a specific slot"""
    try:
        import json
        data = json.loads(request.body)
        
        court_id = data.get('court_id')
        date_str = data.get('date')
        start_time_str = data.get('start_time')
        end_time_str = data.get('end_time')
        
        # Parse date and times
        booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        start_time = datetime.strptime(start_time_str, '%H:%M').time()
        end_time = datetime.strptime(end_time_str, '%H:%M').time()
        
        court = Court.objects.get(id=court_id)
        
        # Add to waitlist
        waitlist_entry = WaitlistService.add_to_waitlist(
            request.user, court, booking_date, start_time, end_time
        )
        
        if waitlist_entry:
            position = WaitlistService.get_waitlist_position(
                request.user, court, booking_date, start_time, end_time
            )
            
            return JsonResponse({
                'success': True,
                'message': f'You have been added to the waitlist (Position: {position})',
                'position': position
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'You are already in the waitlist for this slot'
            }, status=400)
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@require_http_methods(["POST"])
def remove_from_waitlist(request):
    """Remove user from waitlist"""
    try:
        import json
        data = json.loads(request.body)
        
        waitlist_id = data.get('waitlist_id')
        
        if WaitlistService.remove_from_waitlist(waitlist_id, request.user):
            return JsonResponse({
                'success': True,
                'message': 'Removed from waitlist successfully'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Waitlist entry not found'
            }, status=404)
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@require_http_methods(["POST"])
def cancel_booking(request):
    """Cancel a booking and notify next person in waitlist"""
    try:
        import json
        data = json.loads(request.body)
        
        booking_id = data.get('booking_id')
        
        with transaction.atomic():
            booking = Booking.objects.select_for_update().get(
                id=booking_id,
                user=request.user,
                status='CONFIRMED'
            )
            
            # Store booking details for waitlist notification
            court = booking.court
            date = booking.date
            start_time = booking.start_time
            end_time = booking.end_time
            
            # Cancel the booking
            booking.status = 'CANCELLED'
            booking.save()
            
            # Notify next person in waitlist
            notified = WaitlistService.notify_next_in_queue(
                court, date, start_time, end_time
            )
            
            message = 'Booking cancelled successfully'
            if notified:
                message += f'. {notified.user.username} has been notified about the available slot.'
            
            return JsonResponse({
                'success': True,
                'message': message
            })
    
    except Booking.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Booking not found or already cancelled'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

