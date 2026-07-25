import { CAR_MAKES, CAR_MAKES_MODELS } from '../data/carMakesModels'

export interface VehicleOption {
  label: string
  /** True if this entry only exists because a user confirmed it — not part of the static curated list. */
  isCustom: boolean
}

function mergeOptions(staticList: string[], customList: string[]): VehicleOption[] {
  const seen = new Set<string>()
  const result: VehicleOption[] = []
  for (const label of staticList) {
    seen.add(label.toLowerCase())
    result.push({ label, isCustom: false })
  }
  for (const label of customList) {
    const key = label.toLowerCase()
    if (seen.has(key)) continue
    seen.add(key)
    result.push({ label, isCustom: true })
  }
  return result.sort((a, b) => a.label.localeCompare(b.label))
}

export function mergeMakeOptions(customMakes: string[]): VehicleOption[] {
  return mergeOptions(CAR_MAKES, customMakes)
}

export function mergeModelOptions(make: string, customModels: string[]): VehicleOption[] {
  return mergeOptions(CAR_MAKES_MODELS[make] ?? [], customModels)
}
