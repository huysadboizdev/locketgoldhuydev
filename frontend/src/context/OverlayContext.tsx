import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';

export type OverlayKind = 'dialog' | 'announcement';

interface OverlayLayer {
  id: string;
  kind: OverlayKind;
}

interface OverlayContextValue {
  registerLayer: (id: string, kind: OverlayKind) => void;
  unregisterLayer: (id: string) => void;
  getLayerIndex: (id: string) => number;
  isTopLayer: (id: string) => boolean;
  hasBlockingDialog: boolean;
}

const OverlayContext = createContext<OverlayContextValue | null>(null);

export const OverlayProvider: React.FC<React.PropsWithChildren> = ({ children }) => {
  const [layers, setLayers] = useState<OverlayLayer[]>([]);

  const registerLayer = useCallback((id: string, kind: OverlayKind) => {
    setLayers((current) => {
      const existing = current.find((layer) => layer.id === id);
      if (existing?.kind === kind) return current;
      return [...current.filter((layer) => layer.id !== id), { id, kind }];
    });
  }, []);

  const unregisterLayer = useCallback((id: string) => {
    setLayers((current) => current.filter((layer) => layer.id !== id));
  }, []);

  const getLayerIndex = useCallback(
    (id: string) => layers.findIndex((layer) => layer.id === id),
    [layers]
  );

  const isTopLayer = useCallback(
    (id: string) => layers.length > 0 && layers[layers.length - 1]?.id === id,
    [layers]
  );

  const value = useMemo<OverlayContextValue>(
    () => ({
      registerLayer,
      unregisterLayer,
      getLayerIndex,
      isTopLayer,
      hasBlockingDialog: layers.some((layer) => layer.kind === 'dialog'),
    }),
    [getLayerIndex, isTopLayer, layers, registerLayer, unregisterLayer]
  );

  return <OverlayContext.Provider value={value}>{children}</OverlayContext.Provider>;
};

export const useOverlay = (): OverlayContextValue => {
  const context = useContext(OverlayContext);
  if (!context) throw new Error('useOverlay must be used within OverlayProvider');
  return context;
};
