#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通过编码转换修复乱码
原理：UTF-8 字节被错误解释为 Latin-1 编码
修复方法：将乱码字符编码为 Latin-1，然后解码为 UTF-8
"""

import codecs

# 读取文件原始字节
with open('city/agents/planning_agent.py', 'rb') as f:
    raw_bytes = f.read()

# 移除 BOM
has_bom = raw_bytes.startswith(b'\xef\xbb\xbf')
if has_bom:
    raw_bytes = raw_bytes[3:]

# 解码为字符串（使用 UTF-8）
content = raw_bytes.decode('utf-8', errors='replace')

# 需要修复的乱码字符范围（CJK 扩展区或其他非标准字符）
# 这些字符的 Unicode 码点与对应的 UTF-8 字节有特定关系

# 构建反向映射表
# 乱码字符的码点 = 原 UTF-8 字节被解释为 Latin-1 后的字符
reverse_fix = {}

# 常见的中文字符在 UTF-8 中的字节表示
common_chars = """
路网规划智能体人口驱动城市演化版基于密度自动扩展的网络智能体采用网格状布局避免长条化专注于道路网络扩展与城市规划智能体协同工作每个节点有一定人口容量车辆代表人口通勤者当人口密度超过阈值城市扩张添加新节点自动在OD对之间生成通勤车辆
create_new_region方法创建一个新区域显示规划智能体的决策状态方法一个节点接入点和距离间隔方向坐标模拟全局最优路网统计数据结构功能区域规划智能的体的存储记录检查预警提示信息错误成功失败开始暂停继续重新初始设置获取更改修改判断处理执行操作方法属性参数返回结果值类型对象实例继承实现抽象基类模块函数字符串列表字典元组集合整数日期时间文件目录路径名称大小形式格式编解码压缩解压加密解密签名验证权限用户密码登录注销注册管理配置环境系统平台应用程序网络服务客户备份恢复同步异步并行线程进程调度优化加速性能效率速度响应容量阈值监控报警日志跟踪调试测试确保确认取消撤销重做错复制选择全部部分单个多个数量总数平均最大差异比例百分比较区分过滤排序分组分类搜索匹配替换插入合并拆分连接重启保存清空重置向上向下向左向右前进后退左转右转停止加速减速变换转换改变调整控制监视交流合作协作协调组织重点核心关键主要次要重要紧急第一第二第三最后开始完成正常异常错误问题解决应对防止消除减少增加提高降低改善完善加强减弱保持维护修复升级替代取代被取
创建示例性和可达性约束整体输出JSON格式返回请坐整体理由优先连接负载较低距离控制太宽上下太高左右均衡可向任何方向扩展现有信息规划约東避免长条化网格布局可达性折分小时段早高晚低峰非通勤旁区域行倍数比例常医疗机教育构绿商地带工业混合办公购物政府构出发目的地模拟仿真内部生成删除更新决策判断阶段初始发展成熟计算当前统计获取分析形状指标感知状态是否决定已最佳无需扩张拥或饱和需添加传统中心少无连接应先然后考虑密度沿已有延吸引子式半随机游走智能测确定编号类型边车道数位置理由归档相关大模型文解析失败回退附近过大截断可行候选平均选取寻找检查近似平行且距离很近断开网络如果会则移除冗余简化拓扑合并平行边断开阈超时秒数
"""

for char in common_chars:
    char = char.strip()
    if not char:
        continue
    # 获取 UTF-8 字节
    utf8_bytes = char.encode('utf-8')
    # 将这些字节解释为 Latin-1
    try:
        garbled = utf8_bytes.decode('latin-1')
        for g in garbled:
            reverse_fix[g] = char
    except:
        pass

# 应用修复
result = []
for char in content:
    if char in reverse_fix:
        result.append(reverse_fix[char])
    else:
        result.append(char)

fixed_content = ''.join(result)

# 保存修复后的文件
output_bytes = fixed_content.encode('utf-8')
if has_bom:
    output_bytes = b'\xef\xbb\xbf' + output_bytes

with open('city/agents/planning_agent.py', 'wb') as f:
    f.write(output_bytes)

print(f"修复完成！处理了 {len(reverse_fix)} 个字符映射")
