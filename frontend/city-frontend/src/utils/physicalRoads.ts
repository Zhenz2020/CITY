import { Network } from '../types';

export interface PhysicalRoad {
  pairKey: string;
  fromNodeId: string;
  toNodeId: string;
  forwardEdgeId: string;
  reverseEdgeId?: string;
  forwardLanes: number;
  reverseLanes: number;
  totalLanes: number;
}

export const buildPhysicalRoadKey = (fromNodeId: string, toNodeId: string) =>
  [fromNodeId, toNodeId].sort().join('::');

export const buildPhysicalRoads = (network: Network): PhysicalRoad[] => {
  const roads: PhysicalRoad[] = [];
  const visited = new Set<string>();
  const edgeByDirection = new Map(network.edges.map(edge => [`${edge.from_node}->${edge.to_node}`, edge]));

  network.edges.forEach(edge => {
    const pairKey = buildPhysicalRoadKey(edge.from_node, edge.to_node);
    if (visited.has(pairKey)) {
      return;
    }
    visited.add(pairKey);

    const reverseEdge = edgeByDirection.get(`${edge.to_node}->${edge.from_node}`);
    const forwardLanes = Math.max(1, edge.num_lanes || 1);
    const reverseLanes = Math.max(0, reverseEdge?.num_lanes || 0);

    roads.push({
      pairKey,
      fromNodeId: edge.from_node,
      toNodeId: edge.to_node,
      forwardEdgeId: edge.id,
      reverseEdgeId: reverseEdge?.id,
      forwardLanes,
      reverseLanes,
      totalLanes: forwardLanes + reverseLanes,
    });
  });

  return roads;
};
