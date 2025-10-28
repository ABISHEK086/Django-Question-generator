from django.contrib.auth.models import AbstractUser         
from django.db import models   
import json   
  
class User(AbstractUser):
    ROLE_CHOICES = [
        ('student', 'Student'),
        ('staff', 'Staff'), 
        ('admin', 'Admin'),
    ]
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='student')
    
    def __str__(self):
        return f"{self.username} ({self.role})"

class Subject(models.Model):
    name = models.CharField(max_length=32)
    
    def __str__(self):
        return f"{self.name}"
    
class Topic(models.Model):
    name = models.CharField(max_length=32)
    sub = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='subject')
    
    def __str__(self):
        return f"{self.sub} : {self.name}"
    
class QPattern(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="usr")
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='topic')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='sub', default=0)
    imgurl = models.CharField(max_length=128, blank=True)
    question = models.TextField(default="N/A")
    answer = models.TextField(default="N/A",blank=True)
    marks = models.IntegerField(default=0)
    difficulty = models.IntegerField(default=1)
    co = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.topic} : {self.question}"

class StudentGeneratedPaper(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='generated_papers')
    title = models.CharField(max_length=255)
    total_marks = models.IntegerField()
    number_of_questions = models.IntegerField()
    question_ids = models.TextField()  # Store question IDs as JSON
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)  # Add this field
    
    def get_question_ids(self):
        """Return question IDs as list"""
        try:
            return json.loads(self.question_ids)
        except:
            return []
    
    def set_question_ids(self, ids_list):
        """Set question IDs from list"""
        self.question_ids = json.dumps(ids_list)
    
    def get_questions(self):
        """Return actual question objects"""
        from django.core.exceptions import ObjectDoesNotExist
        question_ids = self.get_question_ids()
        questions = []
        for qid in question_ids:
            try:
                question = QPattern.objects.get(id=qid)
                questions.append(question)
            except ObjectDoesNotExist:
                continue
        return questions
    
    def __str__(self):
        return f"{self.title} - {self.student.username}"
