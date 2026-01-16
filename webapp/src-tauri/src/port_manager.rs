use std::net::{SocketAddr, TcpListener};

/// 查找可用的端口号
///
/// 从指定端口开始，递增查找可用的端口
///
/// # 参数
/// * `start_port` - 起始端口号
///
/// # 返回
/// 返回找到的可用端口号，如果全部端口被占用返回 None
pub fn find_available_port(start_port: u16) -> Option<u16> {
    const MAX_ATTEMPTS: u16 = 100;

    for port in start_port..(start_port + MAX_ATTEMPTS) {
        let addr = format!("127.0.0.1:{}", port);

        match addr.parse::<SocketAddr>() {
            Ok(socket_addr) => {
                match TcpListener::bind(&socket_addr) {
                    Ok(_) => {
                        // 成功绑定，端口可用
                        return Some(port);
                    }
                    Err(_) => {
                        // 端口被占用，继续尝试下一个
                        continue;
                    }
                }
            }
            Err(_) => {
                continue;
            }
        }
    }

    None
}

/// 检查指定端口是否可用
///
/// # 参数
/// * `port` - 要检查的端口号
///
/// # 返回
/// 端口可用返回 true，否则返回 false
pub fn is_port_available(port: u16) -> bool {
    let addr = format!("127.0.0.1:{}", port);

    match addr.parse::<SocketAddr>() {
        Ok(socket_addr) => TcpListener::bind(&socket_addr).is_ok(),
        Err(_) => false,
    }
}

#[tauri::command]
pub fn get_available_port(start_port: u16) -> Option<u16> {
    find_available_port(start_port)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_find_available_port() {
        // 测试查找可用端口
        let port = find_available_port(5002);
        assert!(port.is_some(), "应该能找到可用端口");
        assert!(port.unwrap() >= 5002, "端口号应该 >= 5002");
    }

    #[test]
    fn test_is_port_available() {
        // 测试端口可用性检查
        // 大多数情况下，高端口应该是可用的
        let available = is_port_available(59999);
        assert!(available, "高端口 59999 应该可用");
    }

    #[test]
    fn test_port_range() {
        // 测试端口范围查找
        if let Some(port) = find_available_port(5000) {
            assert!(port >= 5000 && port < 5100, "端口应该在 5000-5099 范围内");
        } else {
            panic!("无法找到可用端口");
        }
    }
}
