# -*- coding:utf-8 -*-

import socket
import os
import json
import logging
import logging.config


def init_log_file(app_base_path):
    log_parent_dir = os.path.join(app_base_path, 'log')
    if not os.path.exists(log_parent_dir):  # 判断并创建日志文件夹
        os.mkdir(log_parent_dir)


def read_config_file(app_base_path, conf_file):
    """
    读取配置文件
    :return: 配置文件的json对象
    """
    config_path = os.path.join(app_base_path, 'conf/' + conf_file)
    conf_file = open(config_path, encoding='utf-8')
    conf_json = json.load(conf_file)
    return conf_json


def pull_code_from_git_server(app_base_path, config_json, client_json):
    """
    执行核心功能
    :param app_base_path: 家目录
    :param config_json: 配置文件的json对象
    :param client_json: 客户端上传的json报文
    :return:
    """
    code_update_flag = False
    is_error_flag = False
    func_msg = ""
    client_addr = client_json.get('client_ip', '未知客户端IP')
    device_name = client_json.get('device', 'curl')
    code_list = config_json.get('code_list', False)
    if not code_list:
        logging.error(str(client_addr) + "  配置文件中待更新代码列表为空！")
        func_msg += "配置文件中待更新代码列表为空！\r\n"
        is_error_flag = True
        return {
            "is_error_flag": is_error_flag,
            "code_update_flag": code_update_flag,
            "func_msg": func_msg
        }

    for item_code in code_list:
        is_pull = item_code.get('is_pull', False)
        title = item_code.get('title', '')
        code_path = item_code.get('code_path', False)
        if not is_pull:  # 代码更新标记关闭，跳到下一个
            logging.info(str(client_addr) + "  " + title + "代码升级已经关闭")
            func_msg += title + "代码升级已经关闭！ \r\n"
            is_error_flag = True
            continue
        if not code_path:  # 代码路径未定义，跳到下一个
            logging.error(str(client_addr) + "  " + title + "代码路径未定义")
            func_msg += title + "代码路径未定义！ \r\n"
            is_error_flag = True
            continue
        if not os.path.exists(code_path):  # 判断代码路径是否存在
            logging.error(str(client_addr) + "  " + title + "代码路径不存在")
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
            if last_count == len(git_commands):
                if 'Already up to date' in command_result or 'Already up-to-date' in command_result or 'Already up to date.' in command_result:
                    logging.info(str(client_addr) + "  " + title + "远程GIT仓库代码没有更新")
                    func_msg += title + "远程GIT仓库代码没有更新！\r\n"
                elif 'Aborting' in command_result:
                    logging.info(str(client_addr) + "  " + title + "与远程GIT仓库代码产生冲突")
                    func_msg += title + "与远程GIT仓库代码产生冲突！\r\n"
                    is_error_flag = True
                else:
                    logging.info(str(client_addr) + "  " + title + "代码更新成功")
                    if device_name == 'siri':
                        func_msg += title + "代码更新成功！\r\n"
                    else:
                        func_msg += title + "代码更新成功！\r\n" + command_result + "\r\n"
                    code_update_flag = True
            else:
                if device_name != 'siri':
                    func_msg += command_result
        after_action = item_code.get('after_action',False)
        if not after_action:
            after_action_execute = os.popen(after_action)
            after_action_result = str(after_action_execute.read())
            func_msg += after_action_result + "\r\n"
    os.chdir(app_base_path)  # 还原目录
    return {"is_error_flag": is_error_flag, "code_update_flag": code_update_flag, "func_msg": func_msg}


def restart_app_server(app_base_path, app_root_path, operate):
    """
    重启APP
    :param app_base_path: 家目录
    :param app_root_path:
    :return:
    """
    if not os.path.exists(app_root_path):  # 判断APP根路径是否存在
        return {"shutdown_result": -1, "start_result": -1, "error_msg": "应用根路径不存在，重启失败！"}
    os.chdir(app_root_path)
    shutdown_result = os.system('docker-compose down')
    if operate == 'restart':
        start_result = os.system('docker-compose up -d')
    elif operate == 'upgrade':
        start_result = os.system('docker-compose up -d')
    os.chdir(app_base_path)  # 还原目录
    return {"shutdown_result": shutdown_result, "start_result": start_result}


def upgrade_server(app_base_path):
    # todo 0 开启日志服务
    log_conf_json = read_config_file(app_base_path, "log.json")
    logging.config.dictConfig(log_conf_json)
    # todo 0.1 开启端口监听
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # 重用ip和端口，解决四次挥手的time_wait状态在占用地址问题
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_conf_json = read_config_file(app_base_path, "server.json")
    server_ip = server_conf_json.get('server_ip', False)
    if not server_ip:
        logging.critical('system: 请在配置文件中配置server_ip[服务监听IP]')
        return False
    server_port = server_conf_json.get('server_port', False)
    if not server_port:
        logging.critical('system: 请在配置文件中配置server_port[服务监听端口]')
        return False
    app_root_path = server_conf_json.get('app_root_path', False)
    if not app_root_path:
        logging.critical('system: 请在配置文件中配置app_root_path[docker-compose.yml所在的路径]')
        return False
    server_socket.bind((server_ip, server_port))
    server_socket.listen(1)  # 只初始化一个监听进程
    # todo 0.1 开启服务
    logging.info('system: 服务开启...')

    while True:
        # todo 1 开启服务监听
        conn, addr = server_socket.accept()

        client_addr = addr[0]
        logging.info(str(client_addr) + " 已连接")

        # todo 2 读取配置文件
        server_conf_json = read_config_file(app_base_path, "server.json")
        server_active = server_conf_json.get('server_active', False)
        # todo 2.1 读取日志配置文件
        log_conf_json = read_config_file(app_base_path, "log.json")
        logging.config.dictConfig(log_conf_json)

        # todo 2.2 判断配置文件里面的启用标记是否生效
        if not server_active:
            logging.info(str(client_addr) + " 远程升级已经关闭")
            conn.send("\n远程升级已关闭！\r\n".encode("utf-8"))
            conn.close()
            logging.info(str(client_addr) + " 已登出")
            continue

        # todo 3 接受客户端数据
        decode_msg = str(conn.recv(1024).decode())
        msg_list = decode_msg.split('\r\n')
        # 校验移动端协议的正确性，只接受post协议
        protocol_type = msg_list[0]
        if not protocol_type.startswith('POST'):
            logging.info(str(client_addr) + " 仅接受POST请求")
            conn.send("\n仅接受POST请求！\r\n".encode("utf-8"))
            conn.close()
            logging.info(str(client_addr) + " 已登出")
            continue
        # todo 3.1 接受并传化客户端json对象 {"device": ["curl","siri","wget"],"operate": ["pull","restart","smart"]}
        try:
            json_centent = msg_list[len(msg_list) - 1]
            if len(json_centent) < 1 or json_centent.find('{') < 0:
                logging.info(str(client_addr) + " 请传递报文")
                conn.send("\n请传递报文！\r\n".encode("utf-8"))
                conn.close()
                logging.info(str(client_addr) + " 已登出")
                continue
            client_data_json = json.loads(json_centent)
        except Exception as ex:
            logging.error(str(client_addr) + "  " + str(ex))
            conn.send("\n传递报文异常！\r\n".encode("utf-8"))
            conn.close()
            logging.info(str(client_addr) + " 已登出")
            continue
        client_data_json['client_ip'] = str(client_addr)
        device = client_data_json.get('device', 'smart')
        if device not in ("curl", "siri", "wget"):
            logging.info(str(client_addr) + " 不支持的device")
            conn.send("\n不支持的device！\r\n".encode("utf-8"))
            conn.close()
            logging.info(str(client_addr) + " 已登出")
            continue
        operate = client_data_json.get('operate', 'smart')

        # todo 4 执行核心功能
        logging.info(str(client_addr) + " 执行核心功能")
        send_to_client_msg = "\n"
        if operate == 'pull':  # 只拉取代码
            return_json = pull_code_from_git_server(app_base_path=app_base_path, config_json=server_conf_json,
                                                    client_json=client_data_json)
            func_msg = return_json.get('func_msg', '从服务器拉取代码异常\r\n')
            code_update_flag = return_json.get('code_update_flag', False)
            is_error_flag = return_json.get('is_error_flag', True)
            if (not code_update_flag) and (not is_error_flag):  # 代码未更新and没有产生错误
                send_to_client_msg += "服务器端代码的远程GIT仓库均没有更新！\r\n"
            else:
                send_to_client_msg += func_msg
            logging.info(str(client_addr) + " " + func_msg)
        elif operate == 'restart':  # 只重启
            return_json = restart_app_server(app_base_path=app_base_path, app_root_path=app_root_path,
                                             operate='restart')
            error_msg = return_json.get('error_msg', False)
            if error_msg:
                logging.info(str(client_addr) + " " + error_msg)
                send_to_client_msg += error_msg
                conn.send(("\n" + send_to_client_msg + "\r\n").encode("utf-8"))
                conn.close()
                logging.info(str(client_addr) + " 已登出")
                continue
            shutdown_result = return_json.get('shutdown_result', -1)
            start_result = return_json.get('start_result', -1)
            log_msg = ""
            if shutdown_result == 0:
                send_to_client_msg += "关闭应用成功，\r\n"
                log_msg += "关闭应用成功，"
            else:
                send_to_client_msg += "关闭应用失败，\r\n"
                log_msg += "关闭应用失败，"
            if start_result == 0:
                send_to_client_msg += "重启应用成功！\r\n"
                log_msg += "重启应用成功！"
            else:
                send_to_client_msg += "重启应用失败！\r\n"
                log_msg += "重启应用失败！"
            logging.info(str(client_addr) + " " + log_msg)
        elif operate == 'smart':  # 智能操作，根据代码更新情况决定是否重启
            return_json = pull_code_from_git_server(app_base_path=app_base_path, config_json=server_conf_json,
                                                    client_json=client_data_json)
            code_update_flag = return_json.get('code_update_flag', False)
            is_error_flag = return_json.get('is_error_flag', True)
            func_msg = return_json.get('func_msg', '从服务器拉取代码异常\r\n')
            log_msg = ""
            if (not code_update_flag) and (not is_error_flag):  # 代码未更新and没有产生错误
                send_to_client_msg += "服务器端代码的远程GIT仓库均没有更新，本次不重启！\r\n"
                log_msg += "服务器端代码的远程GIT仓库均没有更新，本次不重启！"
            else:
                send_to_client_msg += func_msg + "\r\n"
                # 代码有更新，重启并且升级base
                return_json = restart_app_server(app_base_path=app_base_path, app_root_path=app_root_path,
                                                 operate='upgrade')
                error_msg = return_json.get('error_msg', False)
                if error_msg:
                    logging.info(str(client_addr) + " " + error_msg)
                    send_to_client_msg += error_msg
                    conn.send(("\n" + send_to_client_msg + "\r\n").encode("utf-8"))
                    conn.close()
                    logging.info(str(client_addr) + " 已登出")
                    continue
                shutdown_result = return_json.get('shutdown_result', -1)
                if shutdown_result == 0:
                    send_to_client_msg += "关闭应用成功！\r\n"
                    log_msg += "关闭应用成功！"
                else:
                    send_to_client_msg += "关闭应用失败！\r\n"
                    log_msg += "关闭应用失败！"
                start_result = return_json.get('start_result', -1)
                if start_result == 0:
                    send_to_client_msg += "重启应用成功！BASE模块正在升级，请稍后访问！\r\n"
                    log_msg += "重启应用成功！BASE模块正在升级，请稍后访问！"
                else:
                    send_to_client_msg += "重启应用失败！\r\n"
                    log_msg += "重启应用失败！"
            logging.info(str(client_addr) + " " + log_msg)
        else:
            send_to_client_msg += "你期望的操作" + operate + "不支持！请检查！\r\n"
            logging.info(str(client_addr) + " 你期望的操作" + operate + "不支持！请检查！")

        # todo 5 发送核心功能执行结果
        conn.send(send_to_client_msg.encode("utf-8"))
        conn.close()
        logging.info(str(client_addr) + " 已登出")


# 服务入口
if __name__ == '__main__':
    home_path = os.path.dirname(os.path.realpath(__file__))
    init_log_file(app_base_path=home_path)  # 创建日志文件夹
    upgrade_server(home_path)  # 开启升级服务
