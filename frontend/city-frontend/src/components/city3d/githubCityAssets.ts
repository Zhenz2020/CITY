// 3D城市资源定义

export interface BuildingModel {
  groundUrl: string;
  floorUrl?: string;
  roofUrl?: string;
  min: number;
  max: number;
}

export const FLOOR_HEIGHT = 1.5;

// 建筑物类型
export const BUILDING_TYPES: BuildingModel[][] = [
  [
    { groundUrl: 'building_1x1_0_g.glb', roofUrl: 'building_1x1_0_r.glb', min: 1, max: 3 },
    { groundUrl: 'building_1x1_1_g.glb', min: 2, max: 5 },
    { groundUrl: 'building_1x1_2_g.glb', roofUrl: 'building_1x1_2_r.glb', min: 3, max: 8 },
  ],
];

// 树木资源
export const TREES_SMALL = [
  'tree_small_0.glb',
  'tree_small_1.glb',
  'tree_small_2.glb',
];
