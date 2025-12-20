import mysql.connector
from mysql.connector import Error
import os
import sys


def _get_mysql_config():
    """从环境变量读取 MySQL 连接信息，避免把账号密码写死在仓库里。"""
    host = os.getenv('MYSQL_HOST', 'localhost')
    user = os.getenv('MYSQL_USER', 'root')
    password = os.getenv('MYSQL_PASSWORD', '')
    database = os.getenv('MYSQL_DATABASE', 'book_review_system')

    if not password:
        print("❌ 未设置 MYSQL_PASSWORD。")
        print("请先在环境变量或 .env 中配置：")
        print("  MYSQL_HOST=localhost")
        print("  MYSQL_USER=root")
        print("  MYSQL_PASSWORD=你的密码")
        print("  MYSQL_DATABASE=book_review_system")
        sys.exit(1)

    return host, user, password, database

def init_database():
    """初始化数据库"""
    connection = None
    
    try:
        print("🔧 初始化数据库...")
        
        host, user, password, database = _get_mysql_config()

        # 连接 MySQL（先连到 server，不指定 db，确保可以创建库）
        connection = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            auth_plugin='mysql_native_password'
        )
        
        if connection.is_connected():
            cursor = connection.cursor()
            print("✅ 已连接到MySQL服务器")

            # 创建数据库
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {database}")
            print("✅ 数据库创建成功")
            
            cursor.execute(f"USE {database}")
            print("✅ 选择数据库成功")
            
            # 创建表
            create_tables(cursor)
            
            # 插入测试数据
            insert_test_data(cursor)
            
            connection.commit()
            print("✅ 所有操作成功提交")
            
    except Error as e:
        print(f"❌ 数据库连接失败: {e}")
        print("\n请确认 MySQL 已启动，并正确设置 MYSQL_* 环境变量。")
        
        if connection and connection.is_connected():
            connection.close()
        
        sys.exit(1)
        
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
            print("✅ 数据库连接已关闭")

def create_tables(cursor):
    """创建所有表"""
    print("📊 创建表结构...")
    
    tables = [
        # 用户表
        """
        CREATE TABLE IF NOT EXISTS users (
            id INT PRIMARY KEY AUTO_INCREMENT,
            username VARCHAR(50) UNIQUE NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            avatar_url VARCHAR(255) DEFAULT 'default_avatar.jpg',
            is_verified BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
        """,
        
        # 书籍表
        """
        CREATE TABLE IF NOT EXISTS books (
            id INT PRIMARY KEY AUTO_INCREMENT,
            title VARCHAR(255) NOT NULL,
            author VARCHAR(100),
            publisher VARCHAR(100),
            isbn VARCHAR(20) UNIQUE,
            cover_url VARCHAR(255),
            douban_rating DECIMAL(3,1),
            rating_count INT DEFAULT 0,
            page_count INT,
            price DECIMAL(10,2),
            publish_date DATE,
            summary TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
        """,
        
        # 评论表
        """
        CREATE TABLE IF NOT EXISTS comments (
            id INT PRIMARY KEY AUTO_INCREMENT,
            book_id INT NOT NULL,
            platform VARCHAR(20) NOT NULL,
            content TEXT NOT NULL,
            rating INT,
            likes INT DEFAULT 0,
            comment_time DATETIME,
            user_info VARCHAR(100),
            source_url VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        
        # 用户书架表
        """
        CREATE TABLE IF NOT EXISTS bookshelves (
            id INT PRIMARY KEY AUTO_INCREMENT,
            user_id INT NOT NULL,
            book_id INT NOT NULL,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes TEXT
        )
        """
    ]
    
    for i, table_sql in enumerate(tables, 1):
        try:
            cursor.execute(table_sql)
            print(f"✅ 表 {i} 创建成功")
        except Error as e:
            print(f"⚠️  表 {i} 创建失败: {e}")

def insert_test_data(cursor):
    """插入测试数据"""
    print("📝 插入测试数据...")
    
    # 插入测试书籍 - 注意字段顺序要与表结构一致
    test_books = [
        ("三体", "刘慈欣", "重庆出版社", "9787229030933", "http://example.com/santi.jpg", 8.8, 0, 302, 23.00, "2008-01-01", "《三体》是刘慈欣创作的系列长篇科幻小说..."),
        ("活着", "余华", "作家出版社", "9787506365437", "http://example.com/huozhe.jpg", 9.4, 0, 191, 20.00, "2012-01-01", "《活着》是作家余华的代表作之一..."),
        ("百年孤独", "加西亚·马尔克斯", "南海出版公司", "9787544253994", "http://example.com/bainiangudu.jpg", 9.3, 0, 360, 39.50, "2011-01-01", "《百年孤独》是哥伦比亚作家加西亚·马尔克斯创作的长篇小说..."),
        ("Python编程：从入门到实践", "Eric Matthes", "人民邮电出版社", "9787115428028", "http://example.com/python.jpg", 9.1, 0, 459, 89.00, "2016-01-01", "本书是一本针对所有层次的Python读者..."),
        ("小王子", "安托万·德·圣-埃克苏佩里", "人民文学出版社", "9787020042494", "http://example.com/xiaowangzi.jpg", 9.0, 0, 96, 22.00, "2000-01-01", "《小王子》是法国作家安托万·德·圣-埃克苏佩里...")
    ]
    
    insert_book_sql = """
    INSERT INTO books (title, author, publisher, isbn, cover_url, douban_rating, 
                      rating_count, page_count, price, publish_date, summary)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE title=VALUES(title), author=VALUES(author)
    """
    
    success_count = 0
    for book in test_books:
        try:
            cursor.execute(insert_book_sql, book)
            success_count += 1
            print(f"✅ 插入书籍: {book[0]}")
        except Error as e:
            print(f"⚠️  插入书籍失败 {book[0]}: {e}")
            print(f"   数据: {book}")
    
    print(f"✅ 测试数据插入完成，成功 {success_count}/{len(test_books)}")

if __name__ == "__main__":
    init_database()
    print("🎉 数据库初始化完成！")