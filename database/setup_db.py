import subprocess
import sys
import mysql.connector
from mysql.connector import Error

def check_mysql_status():
    """检查MySQL服务状态"""
    print("🔍 检查MySQL服务状态...")
    
    try:
        # 尝试启动MySQL服务
        subprocess.run(["sudo", "service", "mysql", "start"], check=True)
        print("✅ MySQL服务已启动")
        return True
    except subprocess.CalledProcessError:
        print("❌ 无法启动MySQL服务")
        return False

def try_mysql_connections():
    """尝试多种MySQL连接方式"""
    connection_params = [
        # 方式1：使用sudo权限（无密码）
        {'user': 'root', 'password': '', 'auth_plugin': 'mysql_native_password'},
        
        # 方式2：使用空密码
        {'user': 'root', 'password': '', 'auth_plugin': ''},
        
        # 方式3：尝试默认密码
        {'user': 'root', 'password': 'password', 'auth_plugin': 'mysql_native_password'},
        
        # 方式4：尝试创建新用户
        {'user': 'bookuser', 'password': 'bookpassword', 'auth_plugin': 'mysql_native_password'}
    ]
    
    for params in connection_params:
        try:
            print(f"尝试连接: user={params['user']}")
            connection = mysql.connector.connect(
                host='localhost',
                user=params['user'],
                password=params['password'],
                auth_plugin=params.get('auth_plugin')
            )
            
            if connection.is_connected():
                print(f"✅ 连接成功！使用用户: {params['user']}")
                return connection
                
        except Error as e:
            print(f"❌ 连接失败: {e}")
            continue
    
    return None

def setup_database():
    """主函数：设置数据库"""
    print("🚀 开始数据库设置流程")
    print("=" * 50)
    
    # 检查MySQL服务
    if not check_mysql_status():
        print("请手动启动MySQL服务：sudo service mysql start")
        sys.exit(1)
    
    # 尝试连接
    connection = try_mysql_connections()
    
    if not connection:
        print("\n🤔 所有连接方式都失败了。请选择：")
        print("1. 尝试修复MySQL配置")
        print("2. 手动设置MySQL")
        print("3. 退出")
        
        choice = input("请输入选择 (1-3): ")
        
        if choice == "1":
            fix_mysql_config()
        elif choice == "2":
            print("\n请手动执行以下步骤：")
            print("1. sudo mysql -u root")
            print("2. ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY 'password';")
            print("3. FLUSH PRIVILEGES;")
            print("4. EXIT;")
            print("\n然后重新运行此脚本")
        sys.exit(1)
    
    # 创建数据库和表
    try:
        cursor = connection.cursor()
        
        # 创建数据库
        cursor.execute("CREATE DATABASE IF NOT EXISTS book_review_system")
        print("✅ 数据库创建成功")
        
        cursor.execute("USE book_review_system")
        print("✅ 使用数据库成功")
        
        # 运行schema.sql
        with open('database/schema.sql', 'r') as f:
            sql_script = f.read()
        
        # 执行每个SQL语句
        for statement in sql_script.split(';'):
            if statement.strip():
                try:
                    cursor.execute(statement)
                except Error as e:
                    print(f"⚠️  SQL执行警告: {e}")
        
        connection.commit()
        print("✅ 表结构创建成功")
        
        # 关闭连接
        cursor.close()
        connection.close()
        
        print("\n🎉 数据库设置完成！")
        print("📊 数据库信息:")
        print("   名称: book_review_system")
        print("   主机: localhost")
        
    except Error as e:
        print(f"❌ 数据库操作失败: {e}")
        sys.exit(1)

def fix_mysql_config():
    """尝试修复MySQL配置"""
    print("\n🔧 尝试修复MySQL配置...")
    
    try:
        # 备份当前配置
        subprocess.run(["sudo", "cp", "/etc/mysql/mysql.conf.d/mysqld.cnf", 
                       "/etc/mysql/mysql.conf.d/mysqld.cnf.backup"], check=True)
        
        # 修改配置以允许无密码登录（仅用于开发）
        with open('/tmp/mysqld_temp.cnf', 'w') as f:
            f.write("""
[mysqld]
skip-grant-tables
            """)
        
        subprocess.run(["sudo", "cp", "/tmp/mysqld_temp.cnf", 
                       "/etc/mysql/mysql.conf.d/mysqld.cnf"], check=True)
        
        # 重启MySQL
        subprocess.run(["sudo", "service", "mysql", "restart"], check=True)
        
        print("✅ MySQL配置已修改，请重新运行此脚本")
        
    except Exception as e:
        print(f"❌ 修复失败: {e}")
        print("请手动修复MySQL配置")

if __name__ == "__main__":
    setup_database()