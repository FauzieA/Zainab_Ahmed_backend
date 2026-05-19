import json
import hmac
import hashlib
import secrets
from django.conf import settings
from django.core.cache import cache  # <-- Safe storage that survives file saves!
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET, require_http_methods
from django.contrib.auth import authenticate
from .models import ServiceConfiguration, AvailableSlot, BookingRecord
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta  
from django.utils import timezone
from django.core.mail import send_mail
from .calendar_service import generate_google_meet_link  

# --- SECURE TOKEN HELPER FUNCTIONS ---
def set_admin_token(token, username):
    # Store token in local memory cache for 24 hours
    cache.set(f"admin_token_{token}", username, timeout=86400)

def get_admin_user_by_token(token):
    return cache.get(f"admin_token_{token}")

# ==========================================
#           PUBLIC ENDPOINTS          
# ==========================================

@require_GET
def get_booking_meta(request):
    """ Feeds pricing data and active slots to React, auto-expiring stagnant pending reservations """
    
    # 1. PASSIVE EXPIRATION SWEEP: Find pending reservations older than 10 minutes
    expiration_limit = timezone.now() - timedelta(minutes=10)
    stale_bookings = BookingRecord.objects.filter(
        status='PENDING', 
        created_at__lt=expiration_limit
    )
    
    if stale_bookings.exists():
        for b in stale_bookings:
            b.status = 'FAILED'
            b.save()
            
            # Release the slot back into circulation if no other active booking holds it
            # (Checks to prevent edge cases where a slot might be shared in a rare race condition)
            still_held = BookingRecord.objects.filter(
                date_booked=b.date_booked, 
                time_booked=b.time_booked, 
                status='CONFIRMED'
            ).exists()
            
            if not still_held:
                AvailableSlot.objects.filter(
                    date_string=b.date_booked, 
                    time_string=b.time_booked
                ).update(is_booked=False)

    # 2. STANDARD FLOW: Now fetch your freshly cleaned slots
    config = ServiceConfiguration.objects.first()
    if not config:
        config = ServiceConfiguration.objects.create()

    slots = AvailableSlot.objects.filter(is_booked=False)
    slots_data = {}
    for slot in slots:
        if slot.date_string not in slots_data:
            slots_data[slot.date_string] = []
        slots_data[slot.date_string].append(slot.time_string)

    return JsonResponse({
        'service': {
            'title': config.title,
            'type': config.session_type,
            'duration': config.duration,
            'price': float(config.price),
            'currency': config.currency,
            'location': config.location
        },
        'available_slots': slots_data
    })

@csrf_exempt
@require_POST
def create_booking_intent(request):
    """ Logs parent data inputs, registers pending intent, and handles 10-minute holds """
    try:
        data = json.loads(request.body)
        client_email = data.get('email')
        selected_slots = data.get('slots', []) 

        if not client_email or not selected_slots:
            return JsonResponse({'error': 'Missing client email or selected schedules.'}, status=400)

        for slot in selected_slots:
            exists = AvailableSlot.objects.filter(
                date_string=slot.get('date'), 
                time_string=slot.get('time'), 
                is_booked=False
            ).exists()
            if not exists:
                return JsonResponse({'error': "Selected space coordinate is unavailable."}, status=400)

        config = ServiceConfiguration.objects.first()
        if not config:
            config = ServiceConfiguration.objects.create()

        number_of_sessions = len(selected_slots)
        total_amount = config.price * number_of_sessions
        unique_booking_ref = f"BK-{secrets.token_hex(8).upper()}"

        for slot in selected_slots:
            # Reconstruct detailed intake diagnostics block
            notes_payload = (
                f"Challenges: {data.get('intake_notes', 'N/A')}"
            )

            BookingRecord.objects.create(
                booking_reference=unique_booking_ref, 
                client_email=client_email,
                client_name=data.get('client_name'),
                client_phone=data.get('client_phone'),
                child_name=data.get('child_name', ''),
                child_age=int(data.get('child_age')) if data.get('child_age') else None,
                child_gender=data.get('child_gender'),
                school_status=data.get('school_status'),
                intake_notes=notes_payload,
                date_booked=slot.get('date'),
                time_booked=slot.get('time'),
                amount_paid=config.price, 
                status='PENDING'
            )
            
            # Temporary slot lock activation flag
            AvailableSlot.objects.filter(
                date_string=slot.get('date'), 
                time_string=slot.get('time')
            ).update(is_booked=True)

        return JsonResponse({
            'status': 'success',
            'booking_reference': unique_booking_ref,
            'amount': float(total_amount), 
            'currency': config.currency
        }, status=201)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_POST
def paystack_webhook(request):
    """ Webhook catching single transactions and unlocking/emailing associated bookings together """
    payload = request.body
    paystack_signature = request.META.get('HTTP_X_PAYSTACK_SIGNATURE')

    # Sandbox bypass guard for local simulation workflows
    if settings.DEBUG and not paystack_signature:
        return handle_successful_payment_processing(payload, "MOCK_REF_DEMO")

    if not paystack_signature:
        return HttpResponse(status=401)

    # Cryptographic confirmation check using SHA512 signature matching
    computed_signature = hmac.new(
        bytes(settings.PAYSTACK_SECRET_KEY, 'utf-8'),
        msg=payload,
        digestmod=hashlib.sha512
    ).hexdigest()

    if computed_signature != paystack_signature:
        return HttpResponse(status=401)

    return handle_successful_payment_processing(payload)


def handle_successful_payment_processing(payload, mock_ref=None):
    try:
        event_data = json.loads(payload)
    except json.JSONDecodeError:
        return HttpResponse("Invalid JSON payload", status=400)
    
    if event_data.get('event') == 'charge.success':
        data = event_data['data']
        paystack_ref = mock_ref if mock_ref else data.get('reference')
        
        custom_metadata = data.get('metadata', {})
        booking_ref = custom_metadata.get('booking_reference')

        if not booking_ref:
            return HttpResponse("Missing booking reference metadata", status=400)

        # 1. Fetch pending records matching this intent transaction session
        pending_bookings = BookingRecord.objects.filter(
            booking_reference=booking_ref, 
            status='PENDING'
        )
        
        if pending_bookings.exists():
            for booking in pending_bookings:
                # 2. Programmatically request Google Meet room space allocation
                meet_url = generate_google_meet_link(
                    date_str=booking.date_booked,
                    time_str=booking.time_booked,
                    summary=f"1:1 Parenting Consultation - {booking.client_name or 'Parent'}",
                    description=f"Diagnostic Profile Summary Notes:\n{booking.intake_notes}",
                    client_email=booking.client_email
                )

                # Store link alongside intake parameters
                booking.intake_notes = f"{booking.intake_notes}\n\n--- ACCESS URL ---\nGoogle Meet link: {meet_url}"
                booking.status = 'CONFIRMED'
                booking.paystack_reference = paystack_ref
                booking.save()

                # Remove specific coordinate parameters out of public client system circulation
                AvailableSlot.objects.filter(
                    date_string=booking.date_booked, 
                    time_string=booking.time_booked
                ).update(is_booked=True)

                # 3. BUILD AND SEND TRANSACTIONAL CONFIRMATION EMAIL
                email_subject = f"Invitation: 1:1 Parenting Consultation @ {booking.date_booked} {booking.time_booked} (West Africa Time)"
                
                email_body = (
                    f"1:1 Parenting Consultation\n\n"
                    f"Organizer: zainaabahmed05@gmail.com\n\n"
                    f"Join with Google Meet:\n"
                    f"{meet_url}\n\n"
                    f"DESCRIPTION\n"
                    f"This 1:1 consultation is designed to help you navigate your child’s behavior with practical, "
                    f"developmentally appropriate strategies. You’ll leave with clear tools you can start using immediately.\n\n"
                    f"WHO THIS IS FOR\n"
                    f"* Parents of children aged 0–7 years\n"
                    f"* You’re dealing with tantrums, stubbornness, or communication struggles\n"
                    f"* You’ve tried different approaches but nothing seems to work\n"
                    f"* You want structured, realistic guidance, not guesswork\n\n"
                    f"WHAT YOU'LL GET\n"
                    f"* 90-minute private consultation\n"
                    f"* Clear understanding of your child’s behavior\n"
                    f"* Personalized strategies tailored to your situation\n"
                    f"* Practical tools you can apply immediately\n"
                    f"* Post-session summary with action steps\n\n"
                    f"PRE-SESSION GUIDE\n"
                    f"How to prepare:\n"
                    f"1. Think about 2-3 real situations with your child\n"
                    f"2. Be ready to describe what happens before, during and after\n"
                    f"3. Note what you’ve already tried\n\n"
                    f"What to expect:\n"
                    f"* We will identify behavior patterns\n"
                    f"* You will understand the 'why' behind the behavior\n"
                    f"* You will receive practical strategies you can use immediately\n\n"
                    f"Important:\n"
                    f"* Join from a quiet space\n"
                    f"* Be on time to maximize your session\n\n"
                    f"Purchase Reference: {booking_ref}\n"
                    f"Payment Tracking ID: {paystack_ref}\n\n"
                    f"When:\n"
                    f"{booking.date_booked} @ {booking.time_booked} (West Africa Time - Lagos)\n"
                )

                send_mail(
                    subject=email_subject,
                    message=email_body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[booking.client_email],
                    fail_silently=False,
                )

    return HttpResponse(status=200)
# ==========================================
#         ADMINISTRATION ENDPOINTS          
# ==========================================

@csrf_exempt
@require_POST
def admin_token_login(request):
    """ Validates admin credentials and returns a secure workspace token """
    try:
        data = json.loads(request.body)
        username = data.get('username')
        password = data.get('password')
        
        user = authenticate(username=username, password=password)
        if user is not None and user.is_staff:
            token = secrets.token_hex(20)
            set_admin_token(token, user.username) # Save via Cache Registry
            return JsonResponse({'token': token, 'status': 'authenticated', 'username': user.username})
        else:
            return JsonResponse({'error': 'Invalid administrator or staff credentials.'}, status=401)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_GET
def get_admin_dashboard_data(request):
    """ Consolidated endpoint returning all slots and bookings for the Admin Matrix """
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    token = auth_header.replace('Token ', '').strip() if 'Token ' in auth_header else ''
    
    if not token or not get_admin_user_by_token(token):
        return JsonResponse({'error': 'Unauthorized workspace access token.'}, status=401)
        
    slots = AvailableSlot.objects.all().order_by('date_string', 'time_string')
    bookings = BookingRecord.objects.all().order_by('-id')
    
    slots_list = [{
        'id': slot.id,
        'date_string': slot.date_string,
        'time_string': slot.time_string,
        'is_booked': slot.is_booked
    } for slot in slots]
    
    bookings_list = [{
        'id': b.id,
        'booking_reference': b.booking_reference,
        'client_email': b.client_email,
        'client_name': b.client_name or '',
        'client_phone': b.client_phone or '',
        'child_name': b.child_name or '',
        'child_age': b.child_age,
        'child_gender': b.child_gender or '',
        'school_status': b.school_status or '',
        'intake_notes': b.intake_notes or '',
        'date_booked': b.date_booked,
        'time_booked': b.time_booked,
        'status': b.status
    } for b in bookings]
    
    return JsonResponse({
        'slots': slots_list,
        'bookings': bookings_list
    })
@csrf_exempt
@require_POST
def admin_manual_reserve(request):
    """ Allows an admin to instantly reserve a specific slot on behalf of a client """
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    token = auth_header.replace('Token ', '').strip() if 'Token ' in auth_header else ''
    
    if not token or not get_admin_user_by_token(token):
        return JsonResponse({'error': 'Unauthorized.'}, status=401)
        
    try:
        data = json.loads(request.body)
        date_str = data.get('date')
        time_str = data.get('time')
        email = data.get('email', 'admin-manual@workspace.com')
        
        # Pull your brand pricing configuration
        config = ServiceConfiguration.objects.first()
        price = config.price if config else 25000.00
        
        # Verify the slot exists and is open
        slot = AvailableSlot.objects.filter(date_string=date_str, time_string=time_str, is_booked=False).first()
        if not slot:
            return JsonResponse({'error': 'This time slot is unavailable or does not exist.'}, status=400)
            
        unique_ref = f"M-BK-{secrets.token_hex(6).upper()}"
        
        # Assign ALL structural parameters explicitly so the admin matrix displays them perfectly
        BookingRecord.objects.create(
            booking_reference=unique_ref,
            client_email=email,
            client_name=data.get('client_name', 'Admin Manual Override'),
            client_phone=data.get('client_phone', 'N/A'),
            child_name=data.get('child_name', ''),
            child_age=int(data.get('child_age')) if data.get('child_age') else None,
            child_gender=data.get('child_gender', 'Unspecified'),
            school_status=data.get('school_status', 'N/A'),
            intake_notes=data.get('intake_notes', 'Manually logged from administrator command board.'),
            date_booked=date_str,
            time_booked=time_str,
            amount_paid=price,
            status='CONFIRMED' # Instantly mark as paid/confirmed since admin is placing it
        )
        
        # Lock the slot out of circulation
        slot.is_booked = True
        slot.save()
        
        return JsonResponse({'status': 'success', 'booking_reference': unique_ref})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
@csrf_exempt
@require_POST
def admin_blackout_dates(request):
    """ Clear availability and lock down public access for a batch pool of dates """
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    token = auth_header.replace('Token ', '').strip() if 'Token ' in auth_header else ''
    
    if not token or not get_admin_user_by_token(token):
        return JsonResponse({'error': 'Unauthorized workspace access token.'}, status=401)
        
    try:
        data = json.loads(request.body)
        dates = data.get('dates', [])
        
        if not dates:
            return JsonResponse({'error': 'No targeting dates provided.'}, status=400)
            
        # Delete unbooked slots to instantly clear public view availability
        AvailableSlot.objects.filter(date_string__in=dates, is_booked=False).delete()
        
        return JsonResponse({'status': 'success', 'message': 'Selected dates successfully restricted.'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
@csrf_exempt
@require_POST
def admin_create_slot(request):
    """ Matrix Engine: Generates cross-product slots across multiple dates/times """
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    token = auth_header.replace('Token ', '').strip() if 'Token ' in auth_header else ''
    
    if not token or not get_admin_user_by_token(token):
        return JsonResponse({'error': 'Unauthorized workspace access token.'}, status=401)
        
    try:
        data = json.loads(request.body)
        date_strings = data.get('date_strings', [])
        time_strings = data.get('time_strings', [])
        
        if not date_strings or not time_strings:
            return JsonResponse({'error': 'Select at least one Date and one Time block.'}, status=400)
            
        created_count = 0
        for date_str in date_strings:
            for time_str in time_strings:
                exists = AvailableSlot.objects.filter(date_string=date_str, time_string=time_str).exists()
                if not exists:
                    AvailableSlot.objects.create(date_string=date_str, time_string=time_str, is_booked=False)
                    created_count += 1
                    
        return JsonResponse({'status': 'success', 'message': f'Generated {created_count} slots successfully.'}, status=201)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["DELETE"])
def admin_delete_slot(request, slot_id):
    """ Wipes an unbooked slot from public circulation completely """
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    token = auth_header.replace('Token ', '').strip() if 'Token ' in auth_header else ''
    
    if not token or not get_admin_user_by_token(token):
        return JsonResponse({'error': 'Unauthorized workspace access token.'}, status=401)
        
    try:
        slot = AvailableSlot.objects.get(id=slot_id)
        if slot.is_booked:
            return JsonResponse({'error': 'Cannot delete an active booked slot directly.'}, status=400)
        slot.delete()
        return JsonResponse({'status': 'success', 'message': 'Slot destroyed successfully.'})
    except AvailableSlot.DoesNotExist:
        return JsonResponse({'error': 'Slot record not found.'}, status=404)


@csrf_exempt
@require_POST
def admin_cancel_booking(request):
    """ Administrative Cancel: Shifts booking state and restores slot visibility """
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    token = auth_header.replace('Token ', '').strip() if 'Token ' in auth_header else ''
    
    if not token or not get_admin_user_by_token(token):
        return JsonResponse({'error': 'Unauthorized.'}, status=401)
        
    try:
        data = json.loads(request.body)
        booking_id = data.get('booking_id')
        
        booking = BookingRecord.objects.get(id=booking_id)
        booking.status = 'CANCELED'
        booking.save()
        
        AvailableSlot.objects.filter(date_string=booking.date_booked, time_string=booking.time_booked).update(is_booked=False)
        
        return JsonResponse({'status': 'success', 'message': 'Booking canceled; session slot released back to public.'})
    except BookingRecord.DoesNotExist:
        return JsonResponse({'error': 'Booking not found.'}, status=404)


@csrf_exempt
@require_POST
def admin_reschedule_booking(request):
    """ Reschedule Engine: Swaps user registration securely to a new vacant target slot """
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    token = auth_header.replace('Token ', '').strip() if 'Token ' in auth_header else ''
    
    if not token or not get_admin_user_by_token(token):
        return JsonResponse({'error': 'Unauthorized.'}, status=401)
        
    try:
        data = json.loads(request.body)
        booking_id = data.get('booking_id')
        target_slot_id = data.get('target_slot_id')
        
        booking = BookingRecord.objects.get(id=booking_id)
        new_slot = AvailableSlot.objects.get(id=target_slot_id)
        
        if new_slot.is_booked:
            return JsonResponse({'error': 'Target slot is already claimed by another schedule.'}, status=400)
            
        AvailableSlot.objects.filter(date_string=booking.date_booked, time_string=booking.time_booked).update(is_booked=False)
        
        booking.date_booked = new_slot.date_string
        booking.time_booked = new_slot.time_string
        booking.save()
        
        new_slot.is_booked = True
        new_slot.save()
        
        return JsonResponse({'status': 'success', 'message': 'Client session shifted successfully.'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)