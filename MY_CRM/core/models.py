from django.contrib.auth.models import User
from django.db import models

class TicketStatus(models.Model):
    name = models.CharField(max_length=50, unique=True)   
    description = models.CharField(max_length=255, blank=True, null=True)  

    def __str__(self):
        return self.name
    
 
        

class Ticket(models.Model):
    client_name = models.CharField(max_length=100)
    account_number = models.CharField(max_length=20)
    phone_number = models.CharField(max_length=15) 
    description = models.TextField(null=True)
    status = models.ForeignKey(TicketStatus, on_delete=models.SET_NULL, null=True, blank=True, default=1) 
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_tickets")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="created_tickets")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True) 
    

class Comment(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE,  null=True,related_name="comments")
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.author.username}"

class Decision(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE,  null=True,related_name="decisions")
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.author.username}"
    
 