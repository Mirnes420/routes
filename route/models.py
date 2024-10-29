from django.db import models

# Create your models here.

class FuelPrice(models.Model):
    opis_truckstop_id = models.IntegerField()
    truckstop_name = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2)
    rack_id = models.IntegerField()
    retail_price = models.DecimalField(max_digits=6, decimal_places=3)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)  # Add these
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)  # Add these


    def __str__(self):
        return f"{self.truckstop_name} - {self.city}, {self.state}"