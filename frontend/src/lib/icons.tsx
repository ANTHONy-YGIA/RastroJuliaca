import {
  Baby,
  Car,
  CarFront,
  CircleQuestionMark,
  Hammer,
  House,
  Landmark,
  PackageSearch,
  ParkingMeter,
  ShieldExclamationPoint,
  Siren,
  Smartphone,
  Store,
  TriangleExclamationPoint,
  User,
  UserSearch,
  Users,
  Wallet,
  Wrench,
  type LucideIcon,
} from "lucide-react";

const MAP: Record<string, LucideIcon> = {
  car: Car,
  "car-front": CarFront,
  wallet: Wallet,
  "shield-alert": ShieldExclamationPoint,
  users: Users,
  hammer: Hammer,
  "package-search": PackageSearch,
  siren: Siren,
  "user-search": UserSearch,
  landmark: Landmark,
  "circle-help": CircleQuestionMark,
  "square-parking": ParkingMeter,
  wrench: Wrench,
  house: House,
  store: Store,
  smartphone: Smartphone,
  user: User,
  baby: Baby,
  "triangle-alert": TriangleExclamationPoint,
};

export function CategoryIcon({ name, className }: { name: string; className?: string }) {
  const Icon = MAP[name] ?? CircleQuestionMark;
  return <Icon className={className} aria-hidden="true" />;
}
