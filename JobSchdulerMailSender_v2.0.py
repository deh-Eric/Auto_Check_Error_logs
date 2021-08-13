# coding = utf-8

'''
    UPDATE TIME: 2021-08-13 11:00:00    
    # 从config.json里面读取一些配置信息载入进来
    # 每分钟循环一次,查找所有 文件修改时间 是今天的所有文件
    # 对上述文件进行查错，先判断job是否跑完了，如果跑完了再进行查错
    # 如果错误则发送邮件
'''

import os
import re
import json
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from pprint import pprint


def mailSender(mail_user,mail_pass,receivers,err_job_list):
    '''
        邮件发送模块
        params:
            filelist —— 发生错误的文件列表
    '''
    mail_host="smtp.163.com"               # 设置 SMTP 服务器
    sender = mail_user                     # 发送者邮箱

    #创建一个带附件的实例
    message =MIMEText(err_job_list, 'plain', 'utf-8')
    message['From'] = Header("Jobschduler Reminder<jobreminder@163.com>", 'utf-8')
    message['To'] =  Header('JobSchduler UserGroup', 'utf-8')
    message['Subject'] = 'Error occurred for a Jobschduler Job'

    '''
    # 构造附件1，传送当前目录下的 test.txt 文件
    message.attach(MIMEText('Error occurred for Jobschduler job.\nDetail information in attchment file for checking', 'plain', 'utf-8'))
    attachment1 = MIMEText(open('D:/CodeSource/files/schduler.ini', 'rb').read(), 'base64', 'utf-8')
    attachment1["Content-Type"] = 'application/octet-stream'
    attachment1["Content-Disposition"] = 'attachment; filename="errlog.txt"' # 这里的filename可以任意写，写什么名字，邮件中显示什么名字
    message.attach(attachment1)
    '''

    try:
        SMTP_Server = smtplib.SMTP_SSL(host = mail_host) # python 3.7版本后修改,建立SSL连接需要使用SMTP_SSL对象
        SMTP_Server.connect(host = mail_host,port = 465) # 465/994=SSL协议端口号 / 25=非SSL协议端口号
        print('Connect SMTP server Success')
        SMTP_Server.set_debuglevel(1)                    # 打印出与SMTP服务器交互的所有信息
        SMTP_Server.login(mail_user,mail_pass) 
        SMTP_Server.sendmail(from_addr=sender,to_addrs=receivers,msg=message.as_string())
        print ("SUCCESS to Send Mail")
        SMTP_Server.quit()
    except smtplib.SMTPException as err:
        SMTP_Server.quit()
        print ("Error: 无法发送邮件"+str(err))

def load_config_param():
    '''
        读取config.json里面的配置信息
    '''
    with open('./config.json','r') as conf:
        configs = json.load(conf)
    return configs
    

def folderMonitor(logs_path,now_time):
    '''
        监视文件夹内文件修改日期的变化，创建需要发送已经失败的job的 “队列”
        params:
            nowTime —— 当前时间的时间戳
    '''
    ufsdic = {}
    filelist = set() # 用于存储需要查错的文件
    path = logs_path
    for root, dir, files in os.walk(path):
        for file in files:
            full_path = os.path.join(root, file)
            mtime = os.stat(full_path).st_mtime
            mday = time.strftime('%Y-%m-%d',time.gmtime(mtime))
            # print(file,mtime)
            if mday == time.strftime('%Y-%m-%d',time.localtime()) and (file.startswith('task.Mercedes_Start') or file.startswith('task.PRC_Start') or file.startswith('task.Chanel_Start')):
                filelist.add(file)
    return filelist


def errChecker(logs_path,filelist):
    '''
        找出文件中存在的保存信息，并把错误的文件筛选出来
        params: 
            filelist —— 符合条件的文件列表，由folderMonitor生成
    '''
    errfilelist = []
    unfinishlist = []
    path = logs_path
    for logfile in filelist:
        with open(path+'/'+logfile,'r',encoding='gbk') as lf:
            f = lf.read()
            logStatus = re.findall('state=closed',f)
            if len(logStatus) == 0:
                unfinishlist.append(logfile)
                print(f'  --{unfinishlist} is running......')
            else:
                # 收集错误类型，有新的可以持续创建新的变量添加错误类型
                errorException = re.findall('exception',f.lower())                # 报出的Exception错误
                errorDBconnect = re.findall('Error occurred while trying to connect to the database',f)  # 报出的数据库连接错误

                if len(errorException) == 0 and len(errorDBconnect) == 0 :
                    pprint(f'  --Correct File:{logfile}') 
                else:
                    pprint(f'  --Error File:{logfile}')
                    errfilelist.append(logfile)
    return errfilelist,unfinishlist


def generateMailText(err_file_list):
    '''
        生成邮件正文
        将错误的task信息给写入到邮件正文里面去
    '''
    mail_text = ''
    for f in err_file_list:
        mail_text = str(f)+'Error\n'
    return mail_text


def main():
    '''
        主过程
        tips:1.消息队列保存在内存当中
             2.根据不同的客户，设置不同的等待时间，以等待报告完成
        process:
        1.死循环监测文件夹状态，以时间为
        2.如果（1）的消息队列不为空，那么开始扫描消息队列中的文件，检索报错的字段是否出现
        3.根据（2）决定是否发送邮件
    '''
    wait_time = 60
    unfinish_file_list =[]
    now_time = time.time()-86400

    configs = load_config_param()
    
    while(True):
        now_time_fmt = time.strftime('%H:%M:%S', time.localtime(now_time)) # 当前时间的格式化时间，用于判断当前的小时，用于在不必要的时间释放资源
        print(f'----- Now time is: {now_time_fmt} -----')
        
        filelist = set(list(folderMonitor(logs_path = configs['logs_path'], now_time = now_time))+unfinish_file_list)

        if now_time_fmt[:2] in ['00','01','02','03','04','05','06','07','08','09','20','21','22','23']:
            print(f'Sleeping Time: {now_time_fmt}')
            time.sleep(3600)         # 此时间段没有Job在运行,休息一个小时
        else:
            err_file_list,unfinish_file_list = errChecker(logs_path = configs['logs_path'], filelist = filelist)
            now_time = time.time()   # 当前时间的时间戳，用于和文件修改时间做比较，刷新队列
            if len(err_file_list) != 0:

                mailSender(mail_user = configs['mail_user'], mail_pass = configs['mail_pass'], receivers = configs['receivers'], err_job_list = 'Now is testing, String type')

        print('------ A Loop Finished ------\n') # at %s' %time.strftime('%H:%M:%S', time.localtime(now_time)))
        
        time.sleep(wait_time)
        

if __name__ == '__main__':
    main()
