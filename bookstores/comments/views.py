from django.shortcuts import render

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from comments.models import Comments
from books.models import Books
from users.models import Passport
from django.views.decorators.csrf import csrf_exempt
import json
import redis
from utils.decorators import login_required
EXPIRE_TIME = 60*10
pool = redis.ConnectionPool(host='localhost',port=6379,db=2)

redis_db=redis.Redis(connection_pool=pool)
