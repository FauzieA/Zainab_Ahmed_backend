from django.db import models
import uuid

class ServiceConfiguration(models.Model):
    """ Allows the Admin to dynamically adjust pricing and service metadata """
    title = models.CharField(max_length=255, default="1:1 Parenting Consultation")
    session_type = models.CharField(max_length=100, default="Private Session")
    duration = models.CharField(max_length=50, default="1 hr")
    price = models.DecimalField(max_digits=10, decimal_places=2, default=25000.00) 
    currency = models.CharField(max_length=10, default="NGN")
    location = models.CharField(max_length=255, default="Online / Digital Session")
    
    # NEW JSON MATRIX FIELD: Stores dynamic page copywriting text keys matching the frontend schema
    site_content = models.JSONField(default=dict, blank=True)
    
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} - {self.currency} {self.price}"


class AvailableSlot(models.Model):
    """ Admin-managed dates and time slots available for booking """
    date_string = models.CharField(max_length=50) 
    time_string = models.CharField(max_length=50) # e.g., "10:00 AM"
    is_booked = models.BooleanField(default=False)

    class Meta:
        unique_together = ('date_string', 'time_string')

    def __str__(self):
        return f"{self.date_string} @ {self.time_string} [{'Booked' if self.is_booked else 'Free'}]"


class BookingRecord(models.Model):
    """ Tracks customer data, selected slot, and real-time Paystack statuses """
    STATUS_CHOICES = [
        ('PENDING', 'Pending Payment'),
        ('CONFIRMED', 'Confirmed/Paid'),
        ('FAILED', 'Failed/Cancelled'),
    ]

    booking_reference = models.CharField(max_length=100, unique=True, default=uuid.uuid4)
    paystack_reference = models.CharField(max_length=255, blank=True, null=True, unique=True)
    
    # PARENT MATRIX
    client_email = models.EmailField()
    client_name = models.CharField(max_length=255, blank=True, null=True)
    client_phone = models.CharField(max_length=50, blank=True, null=True)
    
    # CHILD METRICS
    child_name = models.CharField(max_length=255, blank=True, null=True) 
    child_age = models.IntegerField(blank=True, null=True)
    child_gender = models.CharField(max_length=50, blank=True, null=True)
    school_status = models.CharField(max_length=255, blank=True, null=True)
    
    # DIAGNOSTIC PROFILE
    intake_notes = models.TextField(blank=True, null=True)
    
    # SCHEDULE DETAILS
    date_booked = models.CharField(max_length=50)
    time_booked = models.CharField(max_length=50)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # VIRTUAL METRICS
    google_meet_link = models.URLField(max_length=500, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.client_name} - {self.date_booked} @ {self.time_booked} [{self.status}]"