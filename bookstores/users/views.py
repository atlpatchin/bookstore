import os


from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render,reverse,redirect
from users.tasks import send_active_email

from bookstores import settings
from order.models import OrderInfo, OrderBooks
from users.models import Passport,Address
from utils.decorators import login_required
import re
import redis
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from itsdangerous import SignatureExpired
def register(request):
    return render(request,'users/register.html')

def register_handle(request):
    username = request.POST.get('user_name')
    password = request.POST.get('pwd')
    email = request.POST.get('email')

    if not all([username,password,email]):
        return render(request,'users/register.html',{'errmsg': '参数不能为空!'})

    if not re.match(r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
        return render(request,'users/register.html',{'errmsg':'邮箱不合法！'})

    try:
        passport = Passport.objects.add_one_passport(username=username, password=password, email=email)
    except Exception as e:
        print('e: ',e)
        return render(request,'users/register.html',{'errmsg':'用户名已经存在！'})
    serializer = Serializer(settings.SECRET_KEY,3600)
    token = serializer.dumps({'confirm':passport.id})
    token = token.decode()
    send_active_email.delay(token,username,email)
    return redirect(reverse('books:index'))


def login(request):
    if request.COOKIES.get('username'):
        username = request.COOKIES.get('username')
        checked='checked'
    else:
        username=''
        checked =''
    context={
        'username':username,
        'checked':checked,
    }
    return render(request,'users/login.html',context)

def login_check(request):
    username=request.POST.get('username')
    password =request.POST.get('password')
    remember=request.POST.get('remember')
    verifycode = request.POST.get('verifycode')
    if not all([username,password,remember,verifycode]):
        return  JsonResponse({'res':2})
    if verifycode.upper()!=request.session['verifycode']:
        return JsonResponse({'res':2})
    passport=Passport.objects.get_one_passport(username=username,password=password)
    if passport:
        next_url = reverse('books:index')
        jres=JsonResponse({'res':1,'next_url':next_url})

        if remember=='true':
            jres.set_cookie('username',username,max_age=7*24*3600)
        else:
            jres.delete_cookie('username')

        request.session['islogin']=True
        request.session['username']=username
        request.session['passport_id']=passport.id
        cache_clean()
        return jres
    else:
        return JsonResponse({'res':0})

def logout(request):
    request.session.flush()
    cache_clean()
    return redirect(reverse('books:index'))
def cache_clean():
    r = redis.StrictRedis(host='localhost',port=6379,db=2)
    for key in r.keys():
        if 'bookstores-index' in key.decode('utf8'):
            print('key:',key)
            r.delete(key)
@login_required
def user(request):
    passport_id =request.session.get('passport_id')
    addr = Address.objects.get_default_address(passport_id=passport_id)

    books_li=[]

    context ={
        'addr':addr,
        'page':'user',
        'books_li':books_li,

    }
    return render(request,'users/user_center_info.html',context)

@login_required
def address(request):
    passport_id = request.session.get('passport_id')
    if request.method =='GET':
        addr = Address.objects.get_default_address(passport_id=passport_id)
        return  render(request,'users/user_center_site.html',{'addr':addr,'address':'address'})
    else:
        recipient_name = request.POST.get('username')
        recipient_addr = request.POST.get('addr')
        zip_code = request.POST.get('zip_code')
        recipient_phone = request.POST.get('phone')
        if not all([recipient_name,recipient_addr,recipient_phone]):
            return render(request,'users/user_center_site.html',{'errmsg':'参数不能为空'})

        Address.objects.get_one_address(passport_id=passport_id,
                                        recipient_name=recipient_name,
                                        recipient_addr=recipient_addr,
                                        recipient_phone=recipient_phone,
                                        zip_code=zip_code
                                        )
        return redirect(reverse('user:address'))


@login_required
def order(request,page):
    passport_id = request.session.get('passport_id')
    order_li = OrderInfo.objects.filter(passport_id=passport_id)
    for order in order_li:
        order_id = order.order_id
        order_books_li = OrderBooks.objects.filter(order_id=order_id)
        for order_books in order_books_li:
            count = order_books.count
            price = order_books.price
            amount = count *price
            order_books.amount =amount
        order.order_books_li = order_books_li
    paginator = Paginator(order_li,3)
    num_pages = paginator.num_pages

    if not page:
        page=1
    if page =='' or int(page)>num_pages:
        page = 1
    else:
        page = int(page)
    order_li = paginator.page(page)

    if num_pages<5:
        pages = range(1,num_pages+1)
    elif page<=3:
        pages = range(1,6)
    elif num_pages-page <=2:
        pages= range(num_pages-4,num_pages+1)
    else:
        pages=range(page-2,page+3)
    context = {
        'order_li':order_li,
        'pages':pages,
    }

    return render(request,'users/user_center_order.html',context)

def verifycode(request):
    from PIL import Image,ImageDraw,ImageFont
    import random
    bgcolor = (random.randrange(20,100),random.randrange(20,100),255)
    width = 100
    height =25
    im = Image.new('RGB',(width,height),bgcolor)
    draw=ImageDraw.Draw(im)
    for i in range(0,100):
        xy=(random.randrange(0,width),random.randrange(0,height))
        fill = (random.randrange(0,255),255,random.randrange(0,255))
        draw.point(xy,fill=fill)
        str1='ABCD123EFGHIJK456LMNOPQRS789TUVWXYZ0'
        rand_str=''
        for i in range(0,4):
            rand_str+=str1[random.randrange(0,len(str1))]
        font = ImageFont.truetype(os.path.join(settings.BASE_DIR,'Ubuntu-RI.ttf'),15)
        fontcolor = (255,random.randrange(0,255),random.randrange(0,255))
        draw.text((5,2),rand_str[0],font=font,fill=fontcolor)
        draw.text((25,2),rand_str[1],font=font,fill=fontcolor)
        draw.text((50,2),rand_str[2],font=font,fill=fontcolor)

        draw.text((75,2),rand_str[3],font=font,fill=fontcolor)
        del draw
        request.session['verifycode']=rand_str
        import io
        buf = io.BytesIO()
        im.save(buf,'png')
        return HttpResponse(buf.getvalue(),'image/png')

def register_active(request,token):
    serializer = Serializer(settings.SECRET_KEY,3600)
    try:
        info=serializer.loads(token)
        passport_id = info['confirm']
        passport = Passport.objects.get(id=passport_id)
        passport.is_active=True
        passport.save()
        return redirect(reverse('user:login'))
    except SignatureExpired:
        return HttpResponse('激活链接已过期')