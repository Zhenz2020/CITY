import { Network, Node, Zone } from '../types';

export interface WorldBounds {
  minX: number;
  maxX: number;
  minY: number;
  maxY: number;
  width: number;
  height: number;
  centerX: number;
  centerY: number;
}

export interface ScreenTransform {
  scale: number;
  offsetX: number;
  offsetY: number;
}

export interface SceneTransform {
  scale: number;
  centerX: number;
  centerY: number;
}

const DEFAULT_BOUNDS: WorldBounds = {
  minX: 0,
  maxX: 1000,
  minY: 0,
  maxY: 1000,
  width: 1000,
  height: 1000,
  centerX: 500,
  centerY: 500
};

const buildBounds = (minX: number, maxX: number, minY: number, maxY: number): WorldBounds => {
  const width = Math.max(1, maxX - minX);
  const height = Math.max(1, maxY - minY);
  return {
    minX,
    maxX,
    minY,
    maxY,
    width,
    height,
    centerX: (minX + maxX) / 2,
    centerY: (minY + maxY) / 2
  };
};

export const getWorldBounds = (
  nodes: Node[],
  options?: {
    padding?: number;
    zones?: Zone[];
  }
): WorldBounds => {
  if (!nodes || nodes.length === 0) {
    return DEFAULT_BOUNDS;
  }

  const padding = options?.padding ?? 0;
  const xs = nodes.map(node => node.x);
  const ys = nodes.map(node => node.y);

  let minX = Math.min(...xs) - padding;
  let maxX = Math.max(...xs) + padding;
  let minY = Math.min(...ys) - padding;
  let maxY = Math.max(...ys) + padding;

  options?.zones?.forEach(zone => {
    if (!zone.bounds) {
      return;
    }
    minX = Math.min(minX, zone.bounds[0] - padding);
    minY = Math.min(minY, zone.bounds[1] - padding);
    maxX = Math.max(maxX, zone.bounds[2] + padding);
    maxY = Math.max(maxY, zone.bounds[3] + padding);
  });

  return buildBounds(minX, maxX, minY, maxY);
};

export const getNetworkBounds = (
  network: Network | null,
  options?: {
    padding?: number;
    zones?: Zone[];
  }
): WorldBounds => {
  if (!network) {
    return DEFAULT_BOUNDS;
  }
  return getWorldBounds(network.nodes, options);
};

export const createScreenTransform = (
  bounds: WorldBounds,
  viewportWidth: number,
  viewportHeight: number,
  padding = 50,
  maxScale = 1
): ScreenTransform => {
  const usableWidth = Math.max(1, viewportWidth - padding * 2);
  const usableHeight = Math.max(1, viewportHeight - padding * 2);
  const scale = Math.max(
    0.01,
    Math.min(usableWidth / bounds.width, usableHeight / bounds.height, maxScale)
  );

  return {
    scale,
    offsetX: padding - bounds.minX * scale,
    offsetY: padding - bounds.minY * scale
  };
};

export const createSceneTransform = (
  bounds: WorldBounds,
  targetSceneSize = 100
): SceneTransform => ({
  scale: Math.max(0.01, Math.min(targetSceneSize / bounds.width, targetSceneSize / bounds.height)),
  centerX: bounds.centerX,
  centerY: bounds.centerY
});
