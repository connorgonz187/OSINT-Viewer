declare module "react-globe.gl" {
  import { Component } from "react";

  interface GlobeProps {
    ref?: any;
    globeImageUrl?: string;
    bumpImageUrl?: string;
    backgroundImageUrl?: string;
    showAtmosphere?: boolean;
    atmosphereColor?: string;
    atmosphereAltitude?: number;
    animateIn?: boolean;
    width?: number;
    height?: number;

    // Points layer
    pointsData?: any[];
    pointLat?: string | ((d: any) => number);
    pointLng?: string | ((d: any) => number);
    pointColor?: string | ((d: any) => string);
    pointRadius?: string | number | ((d: any) => number);
    pointAltitude?: string | number | ((d: any) => number);
    pointLabel?: string | ((d: any) => string);
    pointsMerge?: boolean;
    onPointClick?: (point: any, event: MouseEvent) => void;
    onPointHover?: (point: any | null, prevPoint: any | null) => void;

    // Labels layer
    labelsData?: any[];
    labelLat?: string | ((d: any) => number);
    labelLng?: string | ((d: any) => number);
    labelText?: string | ((d: any) => string);
    labelColor?: string | ((d: any) => string);
    labelSize?: string | number | ((d: any) => number);
    labelDotRadius?: string | number | ((d: any) => number);

    // Arcs layer
    arcsData?: any[];

    // Hex bin layer
    hexBinPointsData?: any[];

    // Custom layer
    customLayerData?: any[];
    customThreeObject?: (d: any) => any;
    customThreeObjectUpdate?: (obj: any, d: any) => void;

    [key: string]: any;
  }

  class GlobeComponent extends Component<GlobeProps> {
    pointOfView(pov: { lat?: number; lng?: number; altitude?: number }, transitionMs?: number): void;
    controls(): any;
    scene(): any;
    camera(): any;
    renderer(): any;
  }

  export default GlobeComponent;
}
