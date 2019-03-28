# -*- coding:utf-8 -*-

import socket
import os
import json
import time
import logging


def init_log_file(app_base_path):
    """
    初始化日志系统
    :return:
    """
    log_date = time.strftime('%Y-%m-%d', time.localtime(time.time()))  # 获取年-月-日
    log_parent_dir = os.path.join(app_base_path, 'log')  # 设置日志文件夹
    log_file_path = os.path.join(app_base_path, 'log/server' + log_date + '.log')  # 命名日志文件
    if not os.path.exists(log_parent_dir):  # 判断并创建日志文件夹
        os.mkdir(log_parent_dir)
    if not os.path.exists(log_file_path):  # 判断并创建日志文件
        f = open(log_file_path, 'ab')
        f.close()
    log_format = "%(asctime)s [%(levelname)s]:\t%(message)s"  # 定义日志格式化输出
    date_format = "%Y-%m-%d(%a)%H:%M:%S"  # 定义日期格式
    logging_filehandler = logging.FileHandler(log_file_path, encoding='utf-8')
    logging_streamhandler = logging.StreamHandler()
    logging.basicConfig(level=logging.DEBUG, format=log_format, datefmt=date_format,
                        handlers=[logging_filehandler, logging_streamhandler])  # 调用
    logging.info('system: 日志系统已加载!')


def read_config_file(app_base_path):
    """
    读取配置文件
    :return: 配置文件的json对象
    """
    config_path = os.path.join(app_base_path, 'conf/server.json')
    server_file_conf = open(config_path, encoding='utf-8')
    server_conf_json = json.load(server_file_conf)
    return server_conf_json


def pull_code_from_git_server(app_base_path, config_json, client_json):
    """
    执行核心功能
    :param app_base_path: 家目录
    :param config_json: 配置文件的json对象
    :param client_json: 客户端上传的json报文
    :return:
    """
    code_update_flag = False
    func_msg = ""
    client_addr = client_json.get('client_ip', '未知客户端IP')
    device_name = client_json.get('device', 'curl')
    code_list = config_json.get('code_list', False)
    if not code_list:
        logging.error(client_addr + "  配置文件中待更新代码列表为空！")
        func_msg += "配置文件中待更新代码列表为空！\r\n"
        return {
            "code_update_flag": code_update_flag,
            "func_msg": func_msg
        }

    for item_code in code_list:
        is_pull = item_code.get('is_pull', False)
        title = item_code.get('title', '')
        code_path = item_code.get('code_path', False)
        if not is_pull:  # 代码更新标记关闭，跳到下一个
            logging.info(client_addr + "  " + title + "代码升级已经关闭")
            func_msg += title + "代码升级已经关闭！ \r\n"
            continue
        if not code_path:  # 代码路径未定义，跳到下一个
            logging.error(client_addr + "  " + title + "代码路径未定义")
            func_msg += title + "代码路径未定义！ \r\n"
            continue
        os.chdir(code_path)
        git_commands = item_code.get('git_commands', ["git pull"])
        last_count = 0
        for single_command in git_commands:
            last_count += 1
            exec_comand = os.popen(single_command)
            comand_result = str(exec_comand.read())
            if last_count == len(git_commands):
                if 'Already up to date' in comand_result or 'Already up-to-date' in comand_result:
                    logging.info(client_addr + "  " + title + "远程GIT仓库代码未更新！")
                    func_msg += title + "远程GIT仓库代码未更新！\r\n"
                else:
                    logging.info(client_addr + "  " + title + "代码更新成功！")
                    if device_name == 'siri':
                        func_msg += title + "代码更新成功！\r\n"
                    else:
                        func_msg += title + "代码更新成功！\r\n" + comand_result + "\r\n"
                    code_update_flag = True
            else:
                if device_name != 'siri':
                    func_msg += comand_result
    os.chdir(app_base_path)  # 还原目录
    return {"code_update_flag": code_update_flag, "func_msg": func_msg}


def restart_app_server(app_base_path, app_root_path, operate):
    """
    重启APP
    :param app_base_path: 家目录
    :param app_root_path:
    :return:
    """
    os.chdir(app_root_path)
    shutdown_result = os.system('docker-compose down')
    if operate == 'restart':
        start_result = os.system('docker-compose up -d')
    elif operate == 'upgrade':
        start_result = os.system('docker-compose -f auto-upgrade.yml up -d')
    os.chdir(app_base_path)  # 还原目录
    return {"shutdown_result": shutdown_result, "start_result": start_result}


def pull_server(app_base_path):
    logging.info('system: 服务开启...')
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # 重用ip和端口，解决四次挥手的time_wait状态在占用地址问题
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_conf_json = read_config_file(app_base_path)
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

    try:
        while True:
            # todo 1 开启服务监听
            conn, addr = server_socket.accept()

            client_addr = addr[0]
            logging.info(str(client_addr) + "  已连接")

            # todo 2 读取配置文件
            server_conf_json = read_config_file(app_base_path)
            server_active = server_conf_json.get('server_active', False)

            # todo 2.1 判断配置文件里面的启用标记是否生效
            if not server_active:
                logging.info(str(client_addr) + "  远程升级已经关闭")
                conn.send("\n远程升级已关闭！\r\n".encode("utf-8"))
                conn.close()
                continue

            # todo 3 接受客户端数据
            decode_msg = str(conn.recv(1024).decode())
            msg_list = decode_msg.split('\r\n')
            # 校验移动端协议的正确性，只接受post协议
            protocol_type = msg_list[0]
            if not protocol_type.startswith('POST'):
                logging.info(str(client_addr) + "  仅接受POST请求")
                conn.send("\n仅接受POST请求！\r\n".encode("utf-8"))
                conn.close()
                continue
            # todo 3.1 接受并传化客户端json对象 {"device": ["curl","siri","wget"],"operate": ["pull","restart","smart"]}
            try:
                json_centent = msg_list[len(msg_list) - 1]
                if len(json_centent) < 1 or json_centent.find('{') < 0:
                    logging.info(str(client_addr) + "  请传递报文\r\n")
                    conn.send("\n请传递报文！\r\n".encode("utf-8"))
                    conn.close()
                    continue
                client_data_json = json.loads(json_centent)
            except Exception as ex:
                logging.error(str(client_addr) + "  " + str(ex))
                conn.send("\n请传递报文！\r\n".encode("utf-8"))
                conn.close()
                continue
            client_data_json['client_ip'] = str(client_addr)
            device = client_data_json.get('device', 'smart')
            if device not in ("curl", "siri", "wget"):
                logging.info(str(client_addr) + "  不支持的device\r\n")
                conn.send("\n不支持的device！\r\n".encode("utf-8"))
                conn.close()
                continue
            operate = client_data_json.get('operate', 'smart')

            # todo 4 执行核心功能
            logging.info(str(client_addr) + "  执行核心功能")
            send_to_client_msg = "\n"
            if operate == 'pull':  # 只拉取代码
                return_json = pull_code_from_git_server(app_base_path=app_base_path, config_json=server_conf_json,
                                                        client_json=client_data_json)
                func_msg = return_json.get('func_msg', '从服务器拉取代码异常\r\n')
                send_to_client_msg += func_msg
            elif operate == 'restart':  # 只重启
                return_json = restart_app_server(app_base_path=app_base_path, app_root_path=app_root_path,
                                                 operate='restart')
                shutdown_result = return_json.get('shutdown_result', -1)
                start_result = return_json.get('start_result', -1)
                if shutdown_result == 0:
                    send_to_client_msg += "关闭应用成功，\r\n"
                else:
                    send_to_client_msg += "关闭应用失败，\r\n"
                if start_result == 0:
                    send_to_client_msg += "重启应用成功！\r\n"
                else:
                    send_to_client_msg += "重启应用失败！\r\n"
            elif operate == 'smart':  # 智能操作，根据代码更新情况决定是否重启
                return_json = pull_code_from_git_server(app_base_path=app_base_path, config_json=server_conf_json,
                                                        client_json=client_data_json)
                code_update_flag = return_json.get('code_update_flag', False)
                func_msg = return_json.get('func_msg', '从服务器拉取代码异常\r\n')
                send_to_client_msg += func_msg + "\r\n"
                if code_update_flag:
                    # 代码有更新，重启并且升级base
                    return_json = restart_app_server(app_base_path=app_base_path, app_root_path=app_root_path,
                                                     operate='upgrade')
                    shutdown_result = return_json.get('shutdown_result', -1)
                    start_result = return_json.get('start_result', -1)
                    if shutdown_result == 0:
                        send_to_client_msg += "关闭应用成功，\r\n"
                    else:
                        send_to_client_msg += "关闭应用失败，\r\n"
                    if start_result == 0:
                        send_to_client_msg += "重启应用成功！BASE模块正在升级，请稍后访问！\r\n"
                    else:
                        send_to_client_msg += "重启应用失败！\r\n"
                else:
                    send_to_client_msg += "代码未更新，本次不重启！\r\n"
            else:
                send_to_client_msg += "你期望的操作不支持！请检查！\r\n"

            # todo 5 发送核心功能执行结果
            conn.send(send_to_client_msg.encode("utf-8"))
            conn.close()
            logging.info(str(client_addr) + "  已登出")

    except Exception as ex:
        logging.error('system: 服务异常...' + str(ex))
    finally:
        server_socket.close()
        logging.info('system: 服务结束...')


# 服务入口
if __name__ == '__main__':
    home_path = os.path.dirname(os.path.realpath(__file__))
    init_log_file(home_path)
    pull_server(home_path)
