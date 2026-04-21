import React from 'react';
import { Card, Empty, List, Space, Tag, Typography } from 'antd';
import { DatabaseOutlined } from '@ant-design/icons';

interface AgentMemoryViewProps {
  agentsWithMemory: any[];
  agentMemories: any[];
}

export const AgentMemoryView: React.FC<AgentMemoryViewProps> = ({
  agentsWithMemory,
  agentMemories,
}) => {
  return (
    <Card title={<><DatabaseOutlined /> Agent Memory</>}>
      {agentsWithMemory.length > 0 ? (
        <List
          dataSource={agentsWithMemory}
          renderItem={(agent) => (
            <List.Item>
              <Space direction="vertical" size={2} style={{ width: '100%' }}>
                <Space wrap>
                  <Tag color="purple">{agent.type || agent.agent_type || 'unknown'}</Tag>
                  <span>{agent.name || agent.id || agent.agent_id}</span>
                  <Tag color={agent.memory_count > 0 ? 'blue' : 'default'}>
                    {agent.memory_count ?? 0} 条记忆
                  </Tag>
                </Space>
                <Typography.Text type="secondary">
                  {agent.memory_summary || '已启用，暂无记忆条目'}
                </Typography.Text>
              </Space>
            </List.Item>
          )}
        />
      ) : (
        <Empty description="没有启用记忆的智能体" />
      )}
    </Card>
  );
};

export default AgentMemoryView;
