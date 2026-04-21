import React from 'react';
import { Card, List, Tag } from 'antd';
import { AgentDecision } from '../types';

interface DecisionLogProps {
  decisions: AgentDecision[];
}

export const DecisionLog: React.FC<DecisionLogProps> = ({ decisions }) => {
  return (
    <Card title="决策日志" size="small" style={{ maxHeight: 300, overflow: 'auto' }}>
      <List
        size="small"
        dataSource={decisions.slice(-20).reverse()}
        renderItem={(item, index) => (
          <List.Item key={index}>
            <div>
              <Tag color="blue">{item.agent_type}</Tag>
              <Tag>{item.decision?.action}</Tag>
              <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>
                {item.decision?.reason}
              </div>
            </div>
          </List.Item>
        )}
      />
    </Card>
  );
};
