from django.core.paginator import Paginator
from django.shortcuts import render_to_response,HttpResponse,redirect
from model import forms,models
import datetime,xlrd,re,os
import django.core.exceptions

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 分类缩写与sort_id的对应关系字典
sort={
    'qt':6,
    'shyp':5,
    'dzyp':4,
    'ywpj':3,
    'sbwj':2,
    'zjxj':1,
}

# 404
def page_not_found(request):
    '''404页面处理'''
    response = render_to_response('404.html')
    response.status_code = 404
    return response

# 500
def server_error(request):
    '''500页面处理'''
    response = render_to_response('500.html')
    response.status_code = 500
    return response

# 登陆页面（新）
def login_view(request):
    # 检查输入的学号/密码正确性
    # 若正确，设置session['sno']
    # 若错误，设置错误类型
    # 返回到登陆界面，错误提示也显示在登陆界面
    context = {}
    if request.method == "POST":
        form = forms.login_form(request.POST)
        if form.is_valid():
            # 表单合法，则会把数据放在表单的cleaned_data中
            cd = form.cleaned_data
            username=cd['username']
            password=cd['password']
            try:
                user_db = models.User.objects.get(sno=username)#连接数据库检查密码正确性
                if user_db.pwd == password:
                    # 密码正确
                    if user_db.tag == 2: # 超级管理员
                        request.session["sno"] = user_db.sno  # 记录用户sno
                        return redirect('/superadmin')

                    if user_db.pwd == user_db.sno:
                        #如果密码为初始密码,则要求用户修改密码并完善个人信息
                        request.session["sno2"] = user_db.sno
                        return redirect('/complete_info')
                    if 'errortype' in request.session:
                        # 若存在错误标记，则删除
                        del request.session['errortype']

                    request.session["sno"] = user_db.sno  # 记录用户sno
                    return redirect('/main') # 登陆成功-跳转到主界面
                        # redirect 只能通过session传递参数
                else:
                    # 密码错误
                    context['error']=True
                    context['pwd_error']=True
                    return render_to_response('log_in.html',context)
            except models.User.DoesNotExist:
                # 用户不存在
                context['error'] = True
                context['no_user']=True
                return render_to_response('log_in.html',context)
        else:
            # 表单不合法
            context['error'] = True
            context['form_rror']=True
            return render_to_response('log_in.html', context)
    else:
        # 非post方式访问log_in.html
        # 1.检查是否已经登陆
        if 'sno' in request.session:
            # 已经登陆-返回主界面
            user_login = models.User.objects.get(sno=request.session['sno'])
            context['user_sno'] = user_login.sno
            context['user_name'] = user_login.name
            return redirect('/main')
        else:
            # 未登陆
            return render_to_response('log_in.html')

# 信息上传页面——upload.html
def upload_view(request):
    if request.method=="POST":
        # 1.创建将要上传的'物品'对象(obj)，并将之上传到数据库
        # 2.更新【物品-用户】表和【分类-物品】表

        # 获取用户输入后的POST表单
        form=forms.objUpload_form(request.POST,request.FILES)# request.FILES是获取imagefield的要求，否则获取不到图片
        
        # 检查表单的合法性
        if form.is_valid():
            obj=models.Object()             # 创建上传的物品的对象
            user_obj=models.UserObject()    # 创建用户-物品对象
            sort_obj=models.SortObject()    # 创建分类-物品对象
            try:
                # ！其实这里有问题，假如用户随意输入的学号是存在于数据库中的，那提交的用户就会变成那个学号，而不一定是登陆的用户本身
                user_db = models.User.objects.get(sno=request.session['sno']) #request.session通过cookie记录用户状态
                user_obj.user=user_db
                context = {}
                context['user'] = user_db
                # 输入物品信息
                nowtime = datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')
                time_for_cmp = str(datetime.datetime.now().date())
                time_input = form.cleaned_data['time'].lstrip('-')
                if time_for_cmp<time_input:
                    context['upload_time_error']=True
                    return render_to_response('upload.html', context)

                obj.id = nowtime                            # 为物品生成一个当前时间的id，作为主键
                obj.name = form.cleaned_data['name']
                obj.time = form.cleaned_data['time']
                obj.position = form.cleaned_data['position']
                obj.dscp = form.cleaned_data['dscp']
                if obj.position=="(请勿为空)" or  obj.dscp=="(请勿为空)":
                    context['upload_fail']=True
                    return render_to_response('upload.html', context)
                if form.cleaned_data['tag']=='lost':
                    obj.tag=False
                else:
                    obj.tag = True
                obj.state = 0  # state=0 未审核状态
                if form.cleaned_data['img']:
                    # 如果有图片上传则执行以下部分
                    obj.img = form.cleaned_data['img']
                    obj.img.name = nowtime+".jpg"# 将图片名称修改为物品id
                obj.save()# 上传物品到数据库
                # 根据物品的种类，上传sortobject

                obj_db = models.Object.objects.get(id=nowtime)# 检查是否物品信息是否上传到数据库（通过搜索数据库中，有无id=nowtime的物品，若没有会被except处理
                user_obj.object=obj_db
                user_obj.save()# 上传 用户-物品记录

                sort_id = sort[form.cleaned_data['categary']]
                sort_db = models.AllSort.objects.get(id=sort_id)
                sort_obj.sort = sort_db
                sort_obj.object = obj_db
                sort_obj.save()# 上传 分类-物品记录

                context['upload_success'] = True

                return render_to_response('upload.html',context)
            except models.User.DoesNotExist:
                # 用户不存在
                return server_error(request)
            except models.AllSort.DoesNotExist:
                # 分类不存在
                return server_error(request)
            except models.Object.DoesNotExist:
                # 物品信息没有存入数据库
                return server_error(request)
            except django.core.exceptions.ValidationError:
                context['error']=True
                return render_to_response('upload.html', context)
        else:
            #表单不合法
            context={}
            try:
                sno_login = request.session["sno"]
            except KeyError:
                return render_to_response('upload.html', context)
            # 已经登陆
            user_login=models.User.objects.get(sno=sno_login)
            context['user']=user_login
            context['upload_fail'] = True

            return render_to_response('upload.html',context)

    else:
        # 处理非POST的情况,返回表单页面，用户输入数据
        context={}
        try:
            sno_login = request.session["sno"]
        except KeyError:
            return render_to_response('upload.html', context)
        # 已经登陆
        user_login = models.User.objects.get(sno=sno_login)
        context['user']=user_login
        if user_login.tag==1:
            # 如果为管理员，计算未审核的信息数
            num_state0 = len(models.Object.objects.filter(state=0))
            if num_state0 > 0:
                context["num_state0"] = num_state0
        return render_to_response('upload.html', context)

#物品详细信息显示
def objShowinfo_view(request,object_id):
    # 管理员按钮处理
    if request.method == "POST":
        command1 = request.POST.getlist("feedback") # 物品未通过-提交反馈信息
        command2 = request.POST.getlist("pass")     # 物品通过
        if len(command1)>0:
            p=models.Object.objects.get(id=str(object_id))
            p.state=-1
            p.save()    # 修改物品状态

            fb_type_id = request.POST.get('fb_radio')
            fb_type = models.feedbackType.objects.get(id=fb_type_id)
            obj_fbType = models.obj_feedbackType()
            obj_fbType.object=p
            obj_fbType.feedbackType = fb_type
            if fb_type_id==0: # 如果反馈信息类型为【其他】则读取管理员输入的提示信息
                obj_fbType.other_info = request.POST.get('other_info')
            obj_fbType.save()   # 保存【物品-反馈信息】对象
            return redirect('../admin')

        elif len(command2)>0:
            p=models.Object.objects.get(id=str(object_id))
            p.state=1
            p.save()
            return redirect('../admin')


    # -----------------主要部分---------------------
    # 1.获得【物品】和发布该信息的【用户】
    # 2.根据【登陆情况】【物品是否审核】及【登陆用户的权限】三者来决定信息的显示规则
    # 3.2019年4月11日 21点17分 增加：当物品未审核通过时，管理员给出的反馈信息

    # step1
    obj_db = models.Object.objects.filter(id=object_id)
    #使用get如果味查询到会抛出异常，filter会返回空的[]
    if(len(obj_db)==0):
        page_not_found(request)
    obj = obj_db[0]
    #列表中的第一个对象
    userobj_db = models.UserObject.objects.get(object=obj.id)   # 上传的物品
    user_db = models.User.objects.get(sno=userobj_db.user.sno)  # 上传者
    #user在UserObject中定义为外键,userobj_db.user返回的是User对象
    context={}
    context['user']=user_db
    context['obj']=obj

    # 若obj.state=-1 则加入反馈信息
    feedbackinfo=''
    try:
        if obj.state==-1:
            obj_feedbackType_db = models.obj_feedbackType.objects.get(object=obj)
            feedbackType = obj_feedbackType_db.feedbackType
            if feedbackType.id==0:# 反馈的信息类型为【其他】,则返回信息为管理员输入的信息
                feedbackinfo = obj_feedbackType_db.other_info
            else:
                feedbackinfo = feedbackType.type
            context['feedbackinfo'] = feedbackinfo
    except models.obj_feedbackType.DoesNotExist:
        context['feedbackinfo'] = "无"


    # 确定物品的类别
    try:
        sortobj_db = models.SortObject.objects.get(object=obj)
        sort = sortobj_db.sort
        context['sort'] = sort.name
    except models.SortObject.DoesNotExist:
        server_error(request)
    # step2
    show_obj=False  # 物品信息显示标记 初始False
    show_user=False # 用户信息显示标记 初始False
    show_feedbackinfo=False # 显示物品审核未通过的反馈信息 初始false

    if 'sno' in request.session:    # 'sno'是当前登陆的用户，是查看这条信息的人
        # 已登录
        user_login = models.User.objects.get(sno=request.session['sno']) # 获得已登录用户信息
        if user_login.tag==1:
            # tag==True 管理员
            # 显示所有
            show_obj=True
            show_user=True
            if obj.state==-1:
                show_feedbackinfo=True
        else:
            # tag==False 普通用户
            # 若上传者和查看者时同一人，也可以直接查看
            if obj.state>0 or request.session['sno']==user_db.sno:
                # 通过审核
                # 显示所有
                show_obj = True
                show_user = True
                if obj.state==-1:
                    show_feedbackinfo = True
            # else:
            # 未通过审核，都为False
    else:
        # 未登陆
        # 仅显示物品信息
        show_obj=True
        user_login = []

    context['show_obj']  = show_obj
    context['show_user'] = show_user
    context['show_feedbackinfo'] = show_feedbackinfo
    context['user_login'] = user_login
    # -----------------主要部分---------------------
    return render_to_response("detail.html",context)

# 个人中心
def profile_view(request,nav_id):
    if 'sno' in request.session:
        try:
            user_login = models.User.objects.get(sno=request.session['sno'])
            if user_login.tag==2: # 如果是超级管理员
                return superadmin(request)
        except models.User.DoesNotExist:
            server_error(request)
#----------分页显示设置---------------
    num_one_page = 6
    button_lost_p='lost_pervious'   # 寻物启事 上一页按钮名
    button_lost_n = 'lost_next'     # 寻物启事 下一页按钮名
    button_found_p='found_pervious' # 失物招领 上一页按钮名
    button_found_n = 'found_next'   # 失物招领 下一页按钮名
#-------------个人用户功能：信息完成与删除------------------
    context = {}
    context["show"]="info" # 默认显示个人信息页面
    if request.method == "POST":
        confirm_delete = request.POST.getlist("button_delete")
        confirm_finish_id = request.POST.getlist("finish_id")
        confirm_finish_obj_id = request.POST.getlist("finish_obj_id")
        confirm_phone = request.POST.getlist("phone")
        confirm_email = request.POST.getlist("email")
        confirm_pwd = request.POST.getlist("pwd")

        confirm_lost_p = request.POST.getlist(button_lost_p)
        confirm_lost_n = request.POST.getlist(button_lost_n)
        confirm_found_p = request.POST.getlist(button_found_p)
        confirm_found_n = request.POST.getlist(button_found_n)

        #哪一个模态框按钮按下,这里的完成是模态对话框中的完成
        if len(confirm_delete)>0 and confirm_delete[0]!='':
            obj_id = str(confirm_delete[0])
            tag = models.Object.objects.get(id=obj_id).tag

            if tag==False:
                context["show"]="lost"  # 设置按下按钮后重新加载profile页面的跳转
            else:
                context["show"]="found"
            models.Object.objects.get(id=obj_id).delete()

            #check_box_list = request.POST.getlist("object")
            #for obj_id in check_box_list:
            #    models.Object.objects.get(id=str(obj_id)).delete()

        elif len(confirm_finish_id)>0 and confirm_finish_obj_id[0]!='':
            #修改taken表和object表
            p=models.Object.objects.get(id=str(confirm_finish_obj_id[0]))

            if p.tag==False:
                context["show"]="lost"  # 设置按下按钮后重新加载profile页面的跳转
            else:
                context["show"]="found"

            if p.state == 0 or p.state == -1:
                pass
            else:
                try:
                    takenrecord = models.TakenRecord()
                    user1 = models.User.objects.get(sno=request.session["sno"])
                    user2 = models.User.objects.get(sno=confirm_finish_id[0])
                    obj = models.Object.objects.get(id=confirm_finish_obj_id[0])
                    takenrecord.user1 = user1
                    takenrecord.user2 = user2
                    takenrecord.object = obj
                    # 更改物品状态
                    p.state = 2
                    p.save()
                    if obj.tag:  # 招领物品
                        takenrecord.tag = False  # 用户2来认领
                    else:
                        takenrecord.tag = True  # 用户2提供失物
                    takenrecord.save()
                except models.User.DoesNotExist:
                    context['input_otherID_wrong']=True

                    #return HttpResponse("The user (id=" + confirm_finish_id[0] + ") doesn't exist in database.")

        elif len(confirm_phone)>0 and confirm_phone[0]!='':
            changePhone(request) # 修改手机信息
            context['changePhone_success']=True

        elif len(confirm_email)>0 and confirm_email[0]!='':
            changeEmail(request) # 修改邮箱信息
            context['changeEmail_success'] = True

        elif len(confirm_pwd)>0 and confirm_pwd[0]!='':
            changePwd(request)   # 修改密码
            context['changePwd_success'] = True

        elif len(confirm_lost_p)>0 or len(confirm_lost_n):
            # 如果是lost页按下，则显示lost页
            context["show"] ="lost"
        elif len(confirm_found_p) > 0 or len(confirm_found_n):
            # 如果是found页按下，则显示found页
            context["show"] ="found"

#------------个人用户功能：个人信息、失物招领、寻物启事的信息显示-----------
    # 1.通过request.session获得登陆用户
    # 2.显示用户得个人信息
    # 3.利用"二级页面"的逻辑，显示用户发表过的信息记录

    try:
        sno_login = request.session["sno"]
    except KeyError:
        # 未登录的情况下，使用session会报错：KeyError
        return render_to_response("profile.html", context)
    # 已登录
    try:
        # step1
        user_login = models.User.objects.get(sno=sno_login)
        context["user"] = user_login  # 将'用户'加入字典中
        if user_login.tag==1:
            # 如果为管理员，计算未审核的信息数
            num_state0 = len(models.Object.objects.filter(state=0))
            if num_state0>0:
                context["num_state0"]=num_state0

        # step2
        userobject_db = models.UserObject.objects.filter(user=user_login)
        lostobjs = []
        foundobjs = []
        for item in userobject_db:# 将所有用户的物品记录放到objs中
            if item.object.tag==False:
                lostobjs.append(item.object)
            elif item.object.tag==True:
                foundobjs.append(item.object)
        lostobjs.sort(key=lambda obj: obj.id, reverse=True)
        foundobjs.sort(key=lambda obj: obj.id, reverse=True)

        if len(lostobjs) == 0:
            context["lost_no_history"] = True
        else:
            # context["lostobjs"] = lostobjs
            context["lostobjs"] = Pagination(request,lostobjs,num_one_page,
                                             'page_lost_profile',button_lost_p,button_lost_n)
        if len(foundobjs) == 0:
            context["found_no_history"] = True
        else:
            # context["foundobjs"] = foundobjs  # 将'记录'加入字典字典
            context["foundobjs"] = Pagination(request,foundobjs,num_one_page,
                                             'page_found_profile',button_found_p,button_found_n)
    except models.User.DoesNotExist:
        server_error(request)
    except models.Object.DoesNotExist:
        server_error(request)

    return render_to_response("profile.html", context)

# 退出按钮
def quit_view(request):
    # 1.清除用户登陆，包括cookie
    # 2.退出后，跳转到主界面（现在先跳转到登陆界面
    del request.session['sno']
    return redirect("/main")

# 主界面
def main_view(request):
    context = {}

    Timetype=0
    if request.POST:
        confirm_tt0 = request.POST.getlist('Timetype0')
        confirm_tt1=request.POST.getlist('Timetype1')
        confirm_tt2 = request.POST.getlist('Timetype2')
        confirm_tt3 = request.POST.getlist('Timetype3')
        confirm_tt4 = request.POST.getlist('Timetype4')
        if len(confirm_tt0)>0:
            Timetype=0
        elif len(confirm_tt1)>0:
            Timetype=1
        elif len(confirm_tt2)>0:
            Timetype=2
        elif len(confirm_tt3)>0:
            Timetype=3
        elif len(confirm_tt4)>0:
            Timetype=4

    num_one_page = 6
    button_lost_p='lost_pervious'   # 寻物启事 上一页按钮名
    button_lost_n = 'lost_next'     # 寻物启事 下一页按钮名
    button_found_p='found_pervious' # 失物招领 上一页按钮名
    button_found_n = 'found_next'   # 失物招领 下一页按钮名


    try:
        lost_db = models.Object.objects.filter(tag=False,state=1)   # 通过审核的寻物启事
        found_db = models.Object.objects.filter(tag=True,state=1)   # 通过审核的失物招领
    except models.Object.DoesNotExist:
        server_error(request)

    lost=list(lost_db)
    found=list(found_db)

    if Timetype:
        # 按时间类型进行筛选
        if Timetype>=0 and Timetype<=4:
            lost  = searchByTimeType(input_objs=lost_db,timeType=Timetype)
            found = searchByTimeType(input_objs=found_db, timeType=Timetype)


    # 物品按时间倒序显示（最近时间优先
    lost.sort(key=lambda obj: obj.id, reverse=True)
    found.sort(key=lambda obj: obj.id, reverse=True)

    context['lost'] = Pagination(request,lost,num_one_page,
                                     'page_lost',button_lost_p,button_lost_n)  # 寻物启事
    context['found'] = Pagination(request,found,num_one_page,
                                     'page_found',button_found_p,button_found_n)  # 失物招领

    # 页数显示设置
    if 'page_lost' in request.session:
        context['page_lost']=request.session['page_lost']
        context['page_lost_all'] = int((len(lost) / (num_one_page+0.5)) + 1)
    if 'page_found' in request.session:
        context['page_found']=request.session['page_found']
        context['page_found_all']=int((len(found)/(num_one_page+0.5))+1)

    if 'sno' in request.session:
        # 用户已登陆
        user_login = models.User.objects.get(sno=request.session['sno'])
        context['user_sno']=user_login.sno
        context['user_name']=user_login.name

        if user_login.tag==1:
            # 如果为管理员，计算未审核的信息数
            num_state0 = len(models.Object.objects.filter(state=0))
            if num_state0>0:
                context["num_state0"] = num_state0


    return render_to_response("main.html", context)

# 分类显示
def sort_view(request,sort_id):

    Timetype=0
    if request.POST:
        confirm_tt0 = request.POST.getlist('Timetype0')
        confirm_tt1=request.POST.getlist('Timetype1')
        confirm_tt2 = request.POST.getlist('Timetype2')
        confirm_tt3 = request.POST.getlist('Timetype3')
        confirm_tt4 = request.POST.getlist('Timetype4')
        if len(confirm_tt0)>0:
            Timetype=0
        elif len(confirm_tt1)>0:
            Timetype=1
        elif len(confirm_tt2)>0:
            Timetype=2
        elif len(confirm_tt3)>0:
            Timetype=3
        elif len(confirm_tt4)>0:
            Timetype=4

    num_one_page = 6 # 一页显示的物品数量
    button_lost_p = 'lost_pervious'  # 寻物启事 上一页按钮名
    button_lost_n = 'lost_next'  # 寻物启事 下一页按钮名
    button_found_p = 'found_pervious'  # 失物招领 上一页按钮名
    button_found_n = 'found_next'  # 失物招领 下一页按钮名

    # 1.根据传递的url sort/(sort_id：一位！字符！),选出所有的物品
    # 2.把通过审核的物品加入显示list

    # step1
    context={}
    objs_lost = []
    objs_found = []

    objs_all = set()
    objs_all.update(models.Object.objects.all())
    objs_all = searchBySortID(objs_all,sort_id) # 筛选所有SortID=sort_id的物品
    for obj in objs_all:
        # 筛选state=1，并进行 失物和寻物的分类
        if obj.state == 1:  # 筛选通过审核且未完成的
            if obj.tag == False:
                objs_lost.append(obj)  # 将所有用户的物品记录放到objs_lost(寻物表)中
            else:  # tag=True
                objs_found.append(obj)  # 将所有用户的物品记录放到objs_found(失物表)中

    if Timetype:
        # 按时间类型进行筛选
        if Timetype>=0 and Timetype<=4:
            objs_lost  = searchByTimeType(input_objs=objs_lost,timeType=Timetype)
            objs_found = searchByTimeType(input_objs=objs_found, timeType=Timetype)

    # 对返回数据按【上传时间】进行排序
    objs_lost.sort(key=lambda obj:obj.id,reverse=True)
    objs_found.sort(key=lambda obj: obj.id,reverse=True)
    num_objs_lost = len(objs_lost)
    num_objs_found = len(objs_found)
    if num_objs_lost == 0:
        context["no_lost"] = True
    else:
        objs_lost = Pagination(request,objs_lost,num_one_page,
                                     'page_second_lost',button_lost_p,button_lost_n)  # 寻物启事
    if num_objs_found == 0:
        context["no_found"] = True
    else:
        objs_found = Pagination(request,objs_found,num_one_page,
                                     'page_second_found',button_found_p,button_found_n)  # 失物招领
    context['objs_lost']=objs_lost
    context['objs_found'] = objs_found

    if 'page_second_lost' in request.session:
        context['page_lost']=request.session['page_second_lost']
        context['page_lost_all'] = int((num_objs_lost / (num_one_page+0.5)) + 1)
    if 'page_second_found' in request.session:
        context['page_found'] = request.session['page_second_found']
        context['page_found_all']=int((num_objs_found/(num_one_page+0.5))+1)

    # 用于导航栏显示用户
    if 'sno' in request.session:
        # 用户已登陆
        user_login = models.User.objects.get(sno=request.session['sno'])
        context['user_sno']=user_login.sno
        context['user_name']=user_login.name

        if user_login.tag==1:
            # 如果为管理员，计算未审核的信息数
            num_state0 = len(models.Object.objects.filter(state=0))
            if num_state0>0:
                context["num_state0"] = num_state0
    return render_to_response('second.html', context)


# 完善用户信息,当用户使用初始密码登陆后需要修改密码及完善个人信息
def complete_view(request):
    if 'sno' in request.session:
        del request.session["sno"]  # 删除sno，防止在填写表单时返回上一级页面，用户已经登陆的情况

    try:
        sno_login = request.session["sno2"]
    except KeyError:
    # 未登录的情况下，使用session会报错：KeyError
        return redirect('/main')

    context = {}
    if request.method == 'GET':
        # 已登录
        form = forms.complete_form()
        context["form"] = form 
        context["user"] = sno_login
        return render_to_response("complete_info.html",context)
    else:
        form = forms.complete_form(request.POST)
        if form.is_valid():
            context["user"] = sno_login
            context["form"] = form
            user = models.User.objects.get(sno=sno_login)
            newpwd1 = form.cleaned_data['pwd1']
            newpwd2 = form.cleaned_data['pwd2']
            if newpwd1 == user.pwd or newpwd1 != newpwd2:#前后两次输入密码不同或者输入密码与原密码相同
                context['password_wrong']=True
                return render_to_response('complete_info.html',context)
            user.pwd = newpwd1
            # user.name = form.cleaned_data['name']
            user.phone = form.cleaned_data['phone']
            user.email = form.cleaned_data['email']
            user.save()
            request.session["sno"] = user.sno   # 重新添加sno
            return redirect('/main')
        else:
            context["form"] = form
            context["user"] = sno_login
            return render_to_response('complete_info.html',context)

# 管理员批量导入用户信息功能
def upload_user(request):
    # 读取特定格式的excel文件
    # 要求用户数据在excel的第一个sheet，第一列【学号】第二列【姓名】，第一行是列名
    # 具体格式见 static/images/demo/upload_user_excel_format.png

    form = forms.UploadFileForm(request.POST, request.FILES)
    if form.is_valid():
        count = 0       # 总的导入用户数
        count_in = 0    # 成功导入的用户数
        file = request.FILES['file']
        try:
            userdata = xlrd.open_workbook(file_contents=file.read())
        except:
            # 捕捉xlrd读取excel的出错
            return "文件打开出错"
        sheet0 = userdata.sheet_by_index(0)   # 选择第一个sheet
        for i in range(1, sheet0.nrows):
            count=count+1 # 总用户数+1
            new_user = models.User()
            sno = str(int(sheet0.cell(i, 0).value))    # 读学号
            try:
                models.User.objects.get(sno=sno)
                # 没有DoseNotExist错误 说明数据库中已经有学号为sno的用户了，不必添加
            except models.User.DoesNotExist:
                new_user.sno = sno
                new_user.name = str(sheet0.cell(i, 1).value)        # 读入姓名
                new_user.pwd = new_user.sno     # 初始密码同学号
                new_user.tag = 0                # 用户权限：普通用户
                new_user.save() # 新用户存入数据库
                count_in = count_in+1# 导入用户数+1
        counts=[]
        counts.append(count)
        counts.append(count_in)
        return counts
# 搜索功能
def search_view(request):
    # 1.根据keyword，从数据库中搜索出所有的物品objs
    # 2.将objs分为失物招领(found)和寻物启事(lost)在二级页面上(second.html)显示
    context = {}
    objs_found = []
    objs_lost = []
    keyword=''

    if 'q' in request.GET:
        # 对物品（object）的名称、地点、描述进行查找
        keyword = str(request.GET['q'])     # 获得搜索关键词
        request.session['keyword'] = keyword
    else:
        if 'keyword' in request.session:
            keyword = request.session['keyword']
    objs = set()  # 创建一个物品集合（set）,保证物品对象不重复
    objs.update(models.Object.objects.all().order_by('id'))

    if re.search(' ', keyword):
        keyword_set = set()
        word = ""
        for i in range(len(keyword)):
            if (keyword[i] != ' '):
                word = word + keyword[i]
            else:
                # 读入空格
                if (word != ""):
                    # 若word不为空,则加入keyword_list
                    keyword_set.add(word)
                    word = ""  # 重置word
            if i + 1 >= len(keyword) and word != "":
                keyword_set.add(word)

        objs = searchByKeyword(objs, keyword_set)
    else:
        objs = searchByKeyword(objs, keyword)

    for obj in objs:
        if obj.state > 0:  # 过滤"未审核""审核未通过"的物品
            if obj.tag == False:
                objs_lost.append(obj)
            else:
                objs_found.append(obj)

    Timetype=0
    if request.POST:
        confirm_tt0 = request.POST.getlist('Timetype0')
        confirm_tt1=request.POST.getlist('Timetype1')
        confirm_tt2 = request.POST.getlist('Timetype2')
        confirm_tt3 = request.POST.getlist('Timetype3')
        confirm_tt4 = request.POST.getlist('Timetype4')
        if len(confirm_tt0)>0:
            Timetype=0
        elif len(confirm_tt1)>0:
            Timetype=1
        elif len(confirm_tt2)>0:
            Timetype=2
        elif len(confirm_tt3)>0:
            Timetype=3
        elif len(confirm_tt4)>0:
            Timetype=4

        if Timetype:
            # 按时间类型进行筛选
            if Timetype >= 0 and Timetype <= 4:
                objs_lost = searchByTimeType(input_objs=objs_lost, timeType=Timetype)
                objs_found = searchByTimeType(input_objs=objs_found, timeType=Timetype)

    # 用second.html显示搜索结果

    num_one_page = 12                   # 一页显示的物品数量
    button_lost_p = 'lost_pervious'     # 寻物启事 上一页按钮名
    button_lost_n = 'lost_next'         # 寻物启事 下一页按钮名
    button_found_p = 'found_pervious'   # 失物招领 上一页按钮名
    button_found_n = 'found_next'       # 失物招领 下一页按钮名

    no_found = False
    no_lost = False

    if 'sno' in request.session:
        user = models.User.objects.get(sno=request.session['sno'])
        context['user_sno'] = user.sno
        context['user_name'] = user.name

    num_objs_lost = len(objs_lost)
    num_objs_found = len(objs_found)

    if num_objs_lost == 0:
        no_lost = True
    else:
        # 排序
        objs_lost.sort(key=lambda obj: obj.id, reverse=True)
        # 分页
        objs_lost = Pagination(request, objs_lost, num_one_page,
                               'page_search_lost', button_lost_p, button_lost_n)  # 寻物启事
    if num_objs_found == 0:
        no_found = True
    else:
        # 排序
        objs_found.sort(key=lambda obj: obj.id, reverse=True)
        # 分页
        objs_found = Pagination(request, objs_found, num_one_page,
                                'page_search_found', button_found_p, button_found_n)

    context['no_found'] = no_found
    context['no_lost'] = no_lost
    context['objs_found'] = objs_found
    context['objs_lost'] = objs_lost
    # 页码设置
    if 'page_search_lost' in request.session:
        context['page_lost'] = request.session['page_search_lost']
        context['page_lost_all'] = int((num_objs_lost / (num_one_page + 0.5)) + 1)
    if 'page_search_found' in request.session:
        context['page_found'] = request.session['page_search_found']
        context['page_found_all'] = int((num_objs_found / (num_one_page + 0.5)) + 1)

    return render_to_response('second.html', context)

# 个人中心--修改密码
def changePwd(request):
    inputpwd = str(request.POST.get('old_pwd_input'))# 获得用户输入的旧密码
    sno = request.session['sno']               # 当前用户学号
    user = models.User.objects.get(sno=sno)    # 当前用户对象

    if user.pwd == inputpwd:
        # 输入密码正确
        newpwd1 = str(request.POST.get('new_pwd_input'))
        newpwd2 = str(request.POST.get('new_pwd_input2'))

        if newpwd1==newpwd2 and newpwd1!=sno:
            # 新密码两次相同，且与学号不同：执行修改操作
            user.pwd=newpwd1
            user.save() # 将修改提交到数据库
            print("密码修改成功")

        else:
            # 不能修改
            print("【两次输入的密码不同】或【输入的密码和初始密码相同（学号）】")
    else:
        # 原密码错误
        print("原密码错误")

# 个人中心--修改手机号
def changePhone(request):
    user = models.User.objects.get(sno=request.session['sno'])
    user.phone = str(request.POST.get('phone_input'))
    user.save()

# 个人中心--修改邮箱
def changeEmail(request):
    user = models.User.objects.get(sno=request.session['sno'])
    user.email = str(request.POST.get('email_input'))
    user.save()

# 管理中心
def admin_view(request):
    context = {}
    context["show"]="review" # 默认显示审核页面
    num_one_page = 12 # 一页显示的物品数量
    button_p = 'pervious'  # 上一页按钮名
    button_n = 'next'  # 下一页按钮名
    button_p_review = 'pervious_review'    # 审核页面-上一页按钮名
    button_n_review = 'next_review'        # 审核页面-下一页按钮名

    if request.method == "POST":
        confirm_delete_obj = request.POST.getlist('delete_obj')
        confirm_button_p = request.POST.getlist(button_p)
        confirm_button_n = request.POST.getlist(button_n)
        confirm_button_p_review = request.POST.getlist(button_p_review)
        confirm_button_n_review = request.POST.getlist(button_n_review)
        if len(confirm_delete_obj)>0:
            context["show"] = "obj"  # 返回所有物品页面
            delete_obj_admin(request)
        if len(confirm_button_p or confirm_button_n)>0:
            context["show"] = "obj"  # 返回所有物品页面
        if len(confirm_button_p_review or confirm_button_n_review):
            context["show"] = "review"  # 返回审核页面

    if 'sno' in request.session:
        user = models.User.objects.get(sno=request.session['sno'])
        if user.tag != 1:
            return page_not_found(request)
        else:
            context['user'] = user
        # 将待审核的物品信息显示到网页上
            obj_review_db = models.Object.objects.filter(state=0)  # 筛选出待审核的物品 state=0
        # 计算管理员未审核的信息数量num_state0
            num_state0 = len(obj_review_db)
            if num_state0 == 0:
                context["review_no_history"] = True
            else:
                obj_review = list(obj_review_db)  # 转成list才能进行排序
                obj_review.sort(key=lambda obj: obj.id, reverse=True)  # 排序
                obj_review = Pagination(request, obj_review, num_one_page,
                     'page_admin_review', button_p_review, button_n_review)  # 分页

                context["obj_review"] = obj_review
                context["num_state0"] = num_state0
                if 'page_admin_review' in request.session:
                    context['page_review'] = request.session['page_admin_review']
                    context['page_all_review'] = int((num_state0 / (num_one_page + 0.5)) + 1)
            # 将所有信息，显示到网页上
            obj_all = models.Object.objects.all().order_by('-id')
            num_obj_all = len(obj_all)
            if num_obj_all > 0:
                obj_all = Pagination(request, obj_all, num_one_page,
                   'page_admin_obj', button_p, button_n) # 分页
            # 页数设置
            if 'page_admin_obj' in request.session:
                context['page'] = request.session['page_admin_obj']
                context['page_all'] = int(( num_obj_all / (num_one_page+0.5)) + 1)

            # 添加认领记录
            record_db = models.TakenRecord.objects.all()
            if len(record_db)>0:
                context["record"]=record_db
            userobj_db = models.UserObject.objects.all()
            if len(userobj_db)>0:
                context["userobj"] = userobj_db

            if len(obj_all) == 0:
                context["no_obj"] = True
            else:
                context["obj_all"] = obj_all
            return render_to_response("admin.html", context)
    else:
        return redirect('../login')


# 管理中心-所有信息删除
def delete_obj_admin(request):
    img_file_path = os.path.join(BASE_DIR,"upload/img/object").replace('\\','/')
    check_box_list = request.POST.getlist("object")
    try:
        for obj_id in check_box_list:
            # 删除数据库数据
            models.Object.objects.get(id=str(obj_id)).delete()

            img_path = img_file_path+'/'+str(obj_id)+".jpg"
            if os.path.exists(img_path):
                # 删除文件
                os.remove(img_path)
            else:
                server_error(request)

    except models.Object.DoesNotExist:
        server_error(request)

# 分页函数
def Pagination(request,obj,k,page_index,button_p,button_n):
    '''
    :param request: 主要是获得request里的session
    :param page_index: session里记录页数的变量(类型:string)
    :param button_p: HTML上一页按钮(类型:string)
    :param button_n: HTML下一页按钮(类型:string)
    :param obj: 带分页的数据集
    :param k: 每页显示的物品数
    :return obj_return: 返回分页后的数据集
    '''

    # 获得当前显示的页数，没有则初始化为1
    if page_index in request.session:
        index  = request.session[page_index]
    else:
        index  = 1
    for key in request.session.keys():
        if str(key).find('page')!=-1:
            # 对于session中所有的page项，重置为1
            request.session[str(key)] = 1

    if request.POST:
        lost_pervious = request.POST.getlist(button_p)   # 上一页
        lost_next = request.POST.getlist(button_n)       # 下一页

        # 判断按下'上一页'还是'下一页'，并对页数加减
        if len(lost_pervious)>0:
            index=index-1
            if index<1:     # 页面越过下界的处理
                index=1
        if len(lost_next)>0:
            index=index+1

    # 利用Paginator()函数进行分页
    paginator = Paginator(obj,k)

    # 页数越过上界的处理
    if index>paginator.num_pages:
        index=paginator.num_pages

    # 修改显示的页数
    obj_return = paginator.page(index)
    # 修改控制页数的session
    request.session[page_index] = index

    return obj_return   # 返回分页后的数据集

def searchByKeyword(input_objs, keyword):
    '''
    :param input_objs: 待检索的物品集合
    :param keyword: 检索关键词
    :return: 检索后的物品集合
    '''
    objs = set()  # 创建一个物品集合（set）,保证物品对象不重复
    if keyword.__class__==str:
        for obj in input_objs:
            # re.search(str1,str2)函数: 在str2中找是否含有str1
            searchByName = re.search(keyword,obj.name)
            searchByDscp = re.search(keyword, obj.dscp)
            searchByPosition = re.search(keyword, obj.position)
            if(searchByName or searchByDscp or searchByPosition ):
                objs.add(obj)
    elif keyword.__class__==set or keyword.__class__==list:
        for word in keyword:
            for obj in input_objs:
                searchByName = re.search(word, obj.name)
                searchByDscp = re.search(word, obj.dscp)
                searchByPosition = re.search(word, obj.position)
                if (searchByName or searchByDscp or searchByPosition):
                    objs.add(obj)

    return list(objs)

def searchBySortID(input_objs,SortID):
    '''
    :param input_objs: 待过滤的物品集合
    :param SortID: 过滤条件：物品分类号
    :return: 过滤后的物品集合
    '''
    objs = set()  # 创建一个物品集合（set）,保证物品对象不重复
    if (SortID.__class__ == str):
        try:
            # 注意返回的sort_id 是个字符，不是数字
            if (SortID=='0'):  # 总览：显示所有分类的object
                sortobj_db=models.SortObject.objects.all().order_by('object__id')
            else:  # 选出特点类型的物品
                sort_for_search = models.AllSort.objects.get(id=SortID)
                sortobj_db = models.SortObject.objects.filter(sort=sort_for_search).order_by('object__id')
        except models.SortObject.DoesNotExist:
            HttpResponse("models.SortObject.DoesNotExist")
        except models.AllSort.DoesNotExist:
            HttpResponse("models.AllSort.DoesNotExist")

        for obj in input_objs:
            for sortobj in sortobj_db:
                if obj.id == sortobj.object.id:
                    objs.add(obj)
                    break

    return list(objs)

def searchByTimeType(input_objs,timeType):
    '''
    根据【提交时间类型】返回物品
    :param input_objs: 待过滤的物品集合
    :param timeType:timeType=0:所有;timeType=1:最近三天 ;
                    timeType=2:最近两周;timeType=3:最近30天;timeType=4:更早
    :return: 过滤后的物品集合
    '''

    objs = []
    objs3 = set()       # 最近三天集合
    objs14 = set()      # 最近两周集合
    objs30 = set()      # 最近30天集合
    objsGT30 = set()    # 更早集合

    nowtime = datetime.datetime.now()
    # 要先获得物品的提交时间 userobject.time
    for obj in input_objs:
        try:
            userobject = models.UserObject.objects.get(object=obj)
            userobject.time=userobject.time.replace(tzinfo=None) #!! 数据库中的时间是有时区（tzinfo）属性的（=UTC）
            daysdelta = (nowtime-userobject.time).days # 计算记录与当前的天数差

            if daysdelta >= 0:
                if daysdelta <= 3:
                    objs3.add(obj)
                    objs14.add(obj)
                    objs30.add(obj)
                elif daysdelta <= 14:
                    objs14.add(obj)
                    objs30.add(obj)
                elif daysdelta <= 30:
                    objs30.add(obj)
                else:  # >30
                    objsGT30.add(obj)

        except models.UserObject.DoesNotExist:
            continue

    if timeType==0:
        objs=list(input_objs)
    elif timeType==1:
        objs=list(objs3)
    elif timeType == 2:
        objs=list(objs14)
    elif timeType==3:
        objs=list(objs30)
    elif timeType==4:
        objs=list(objsGT30)

    return objs

def superadmin(request):
    context={}
    if 'sno' in request.session:
        context['user']=models.User.objects.get(sno=request.session['sno'])
        context['show'] = 'edit'
        if request.POST and ('edit_sno' in request.session):
            user = models.User.objects.get(sno=request.session['edit_sno'])
            confirm_name = request.POST.getlist('name')
            confirm_pwdreset = request.POST.getlist('reset')
            confirm_tag = request.POST.getlist('tag')
            confirm_upload_user = request.POST.getlist('upload_user')

            if len(confirm_name) > 0:
                user.name = str(request.POST.get('name_input'))
                user.save()
                context['info_type1'] = 'success'
                context['info1'] = '用户密码修改成功'

            if len(confirm_pwdreset) > 0:
                user.pwd = user.sno # 将用户密码初始化为学号
                user.save()
                context['info_type1'] = 'success'
                context['info1'] = '用户密码已初始化为学号'

            if len(confirm_tag)> 0 :
                # 修改用户权限
                new_tag = request.POST.get('tag_radio')
                if new_tag == '0':
                    user.tag=0
                elif new_tag == '1':
                    user.tag=1
                user.save()
                context['info_type1'] = 'success'
                context['info1'] = '用户权限修改成功'

            if len(confirm_upload_user) > 0:
                context['show'] = 'upload'
                result = upload_user(request)

                if result.__class__==str:
                    context['info_type'] = 'danger'
                    context['info'] = result
                elif result.__class__==list:
                    if result[0]==result[1]:
                        context['info_type'] = 'success'
                        context['info'] = '成功导入'+str(result)+"个新用户"
                    else:
                        context['info_type'] = 'warning'
                        context['info'] = '成功导入' + str(result[1]) + "个新用户，"\
                                          +str(result[0]-result[1])+"个用户已存在于数据库中"

        if 'q' in request.GET:
            sno = str(request.GET['q'])  # 获得搜索学号
            context['edit_sno']=sno
            try:
                edit_user = models.User.objects.get(sno=sno)
                request.session['edit_sno'] = sno
                context['edit_user'] = edit_user
            except models.User.DoesNotExist:
                context['nfound_edit_user'] = True
    else:
        page_not_found(request)

    return render_to_response('superadmin.html',context)