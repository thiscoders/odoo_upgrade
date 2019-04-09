# -*- coding:utf-8 -*-

import socket
import os
import json
import logging
import logging.config


# 读取配置文件
def read_config_file(app_base_path, conf_file):
    config_path = os.path.join(app_base_path, 'conf/' + conf_file)
    conf_file = open(config_path, encoding='utf-8')
    conf_json = json.load(conf_file)
    return conf_json


# 刷新日志配置
def refresh_log_system(app_base_path):
    os.chdir(app_base_path)
    log_parent_dir = os.path.join(app_base_path, 'log')
    if not os.path.exists(log_parent_dir):  # 判断并创建日志文件夹
        os.mkdir(log_parent_dir)
    log_conf_json = read_config_file(app_base_path, "log.json")
    logging.config.dictConfig(log_conf_json)


# 发送消息到客户端并记录日志
def send_msg_to_client(client_connection, send_msg, client_addr, extra_msg=""):
    logging.info(str(client_addr) + send_msg + extra_msg)
    client_connection.send(("\n" + send_msg + "\r\n").encode("utf-8"))
    client_connection.close()
    logging.info(str(client_addr) + " 已登出")


# 从git服务器拉取代码
def pull_code_from_git_server(config_json, client_json):
    code_update_flag = False  # 是否需要升级标记
    is_error_flag = False  # 是否产生错误标记
    func_msg = ""
    client_operate = client_json.get('operate', False)
    app_name = config_json.get('app_name', False)
    if client_operate in ["no", "restart", "upgrade"]:
        func_msg += app_name + "客户端操作不需要拉取代码！\r\n"
        return {"is_error_flag": is_error_flag, "code_update_flag": code_update_flag, "func_msg": func_msg}
    code_list = config_json.get('code_list', False)
    if not code_list or len(code_list) < 1:
        func_msg += app_name + "的配置文件中待更新代码列表为空！\r\n"
        is_error_flag = True
        return {"is_error_flag": is_error_flag, "code_update_flag": code_update_flag, "func_msg": func_msg}

    device_name = client_json.get('device', 'curl')
    for item_code in code_list:
        is_pull = item_code.get('is_pull', False)
        title = item_code.get('title', '')
        if not is_pull:  # 代码更新标记关闭，跳到下一个
            func_msg += title + "代码升级已经关闭！ \r\n"
            is_error_flag = True
            continue
        code_path = item_code.get('code_path', False)
        if not code_path:  # 代码路径未定义，跳到下一个
            func_msg += title + "代码路径未定义！ \r\n"
            is_error_flag = True
            continue
        if not os.path.exists(code_path):  # 判断代码路径是否存在
            func_msg += title + "代码路径不存在！ \r\n"
            is_error_flag = True
            continue
        os.chdir(code_path)
        git_commands = item_code.get('git_commands', ["git pull"])
        last_count = 0
        for single_command in git_commands:
            last_count += 1
            exec_comand = os.popen(single_command)
            command_result = str(exec_comand.read())
            if last_count == len(git_commands):  # 最后一个git命令必须是git pull ***
                if 'Already up to date' in command_result or 'Already up-to-date' in command_result:
                    func_msg += app_name + "的" + title + "远程GIT仓库代码没有更新！\r\n"
                elif 'Aborting' in command_result:
                    func_msg += app_name + "的" + title + "代码与远程GIT仓库代码产生冲突！\r\n"
                    is_error_flag = True
                else:
                    if device_name == 'siri':
                        func_msg += app_name + "的" + title + "代码更新成功！\r\n"
                    else:
                        func_msg += app_name + "的" + title + "代码更新成功！\r\n" + command_result + "\r\n"
                    code_update_flag = True
            else:
                if device_name != 'siri':
                    func_msg += command_result
    return {"is_error_flag": is_error_flag, "code_update_flag": code_update_flag, "func_msg": func_msg}


# 重启APP
def restart_app_server(config_json, client_json):
    is_error_flag = False
    return_msg = ""
    client_operate = client_json.get('operate', False)
    app_name = config_json.get('app_name', False)
    if client_operate in ["no", "pull"]:
        return_msg += app_name + "不需要重启应用！\r\n"
        return {"is_error_flag": is_error_flag, "return_msg": return_msg}
    app_root_path = config_json.get("app_path", False)
    if not os.path.exists(app_root_path):  # 判断APP根路径是否存在
        is_error_flag = True
        return_msg += app_name + "的应用根路径不存在！\r\n"
        return {"is_error_flag": is_error_flag, "return_msg": return_msg}
    os.chdir(app_root_path)
    shutdown_result = os.system('docker-compose down')
    if shutdown_result == 0:
        return_msg += "关闭应用成功！\r\n"
    else:
        return_msg += "关闭应用失败！\r\n"
    code_update_flag = config_json.get("code_update_flag", False)
    if client_operate == 'restart' or client_operate == 'whos_your_daddy':
        start_result = os.system('docker-compose up -d')
        if start_result == 0:
            return_msg += "重启应用成功！请稍后访问！\r\n"
        else:
            return_msg += "重启应用失败！\r\n"
    elif client_operate == 'upgrade' or (client_operate == 'smart' and code_update_flag is True):
        start_result = os.system('docker-compose -f auto-upgrade.yml up -d')
        if start_result == 0:
            return_msg += "重启应用成功！BASE模块正在升级，请稍后访问！\r\n"
        else:
            return_msg += "重启应用失败！BASE模块不升级！\r\n"
    return {"is_error_flag": is_error_flag, "return_msg": return_msg}


def upgrade_server(app_base_path):
    # 开启日志服务
    refresh_log_system(app_base_path=app_base_path)

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # 重用ip和端口，解决四次挥手的time_wait状态在占用地址问题
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # 读取配置文件，获取监听地址和端口
    server_conf_json = read_config_file(app_base_path, "server.json")
    server_ip = server_conf_json.get('server_ip', False)
    if not server_ip:
        logging.critical('system: 请在配置文件中配置server_ip[服务监听IP]')
        return False
    server_port = server_conf_json.get('server_port', False)
    if not server_port:
        logging.critical('system: 请在配置文件中配置server_port[服务监听端口]')
        return False

    server_socket.bind((server_ip, server_port))
    server_socket.listen(1)  # todo 只初始化一个监听进程

    logging.info('system: 服务开启...')

    while True:
        # todo 1 开启服务监听
        conn, addr = server_socket.accept()
        client_addr = addr[0]
        logging.info(str(client_addr) + " 已连接")
        # todo 1.1 更新日志系统
        refresh_log_system(app_base_path=app_base_path)

        # todo 2 读取配置文件
        server_conf_json = read_config_file(app_base_path, "server.json")
        server_active = server_conf_json.get('server_active', False)
        if not server_active:  # 判断配置文件里面的启用标记是否生效
            send_msg_to_client(client_connection=conn, send_msg="远程升级已关闭！", client_addr=client_addr)
            continue

        # todo 3 接受客户端数据
        decode_msg = str(conn.recv(1024).decode())
        msg_list = decode_msg.split('\r\n')
        if not msg_list[0].startswith('POST'):  # 校验移动端协议的正确性，只接受post协议
            send_msg_to_client(client_connection=conn, send_msg="仅接受POST请求！", client_addr=client_addr)
            continue
        # todo 3.1 接受并传化客户端json对象
        #  {"device": ["curl","siri","wget"],
        #   "which_env": "account",
        #   "operate": ["no","restart","upgrade","pull","whos_your_daddy","smart"]}
        try:
            json_centent = msg_list[len(msg_list) - 1]
            if len(json_centent) < 1 or json_centent.find('{') < 0:
                send_msg_to_client(client_connection=conn, send_msg="请传递报文！", client_addr=client_addr)
                continue
            client_data_json = json.loads(json_centent)
        except Exception as ex:
            send_msg_to_client(client_connection=conn, send_msg="传递报文异常！", client_addr=client_addr, extra_msg=str(ex))
            continue
        client_data_json['client_ip'] = str(client_addr)
        device = client_data_json.get('device', False)
        if device not in ("curl", "siri", "wget"):
            send_msg_to_client(client_connection=conn, send_msg="不支持的设备！", client_addr=client_addr)
            continue
        which_env = client_data_json.get('which_env', False)
        if not which_env:
            send_msg_to_client(client_connection=conn, send_msg="不支持的环境！", client_addr=client_addr)
            continue
        operate = client_data_json.get('operate', False)
        if operate not in ["no", "restart", "upgrade", "pull", "whos_your_daddy", "smart"]:
            send_msg_to_client(client_connection=conn, send_msg="不支持的操作！", client_addr=client_addr)
            continue
        single_conf_json = server_conf_json.get("app_list_json", {}).get(which_env, False)  # 获取环境配置JSON对象
        if not single_conf_json:
            send_msg_to_client(client_connection=conn, send_msg=which_env + "环境不存在！", client_addr=client_addr)
            continue

        send_to_client_msg = "\n"

        pull_code_json = pull_code_from_git_server(config_json=single_conf_json, client_json=client_data_json)
        code_update_flag = pull_code_json.get('code_update_flag', False)
        is_error_flag = pull_code_json.get('is_error_flag', False)
        func_msg = pull_code_json.get('func_msg', False)
        single_app_name = single_conf_json.get('app_name', "未知应用")
        if (not code_update_flag) and (not is_error_flag):  # 代码未更新and没有产生错误
            send_to_client_msg += single_app_name + "的服务器端代码的远程GIT仓库均没有更新！\r\n"
        else:
            send_to_client_msg += func_msg

        single_conf_json['code_update_flag'] = code_update_flag
        restart_app_json = restart_app_server(config_json=single_conf_json, client_json=client_data_json)
        return_msg = restart_app_json.get("return_msg", False)
        send_to_client_msg += return_msg

        # todo 5 发送核心功能执行结果
        conn.send(send_to_client_msg.encode("utf-8"))
        conn.close()
        logging.info(str(client_addr) + " 已登出")


# 服务入口
if __name__ == '__main__':
    home_path = os.path.dirname(os.path.realpath(__file__))
    upgrade_server(home_path)  # 开启升级服务
