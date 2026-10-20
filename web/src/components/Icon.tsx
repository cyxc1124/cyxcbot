import {
  HomeIcon, PlayCircleIcon, VideoCameraIcon, ChatBubbleLeftRightIcon,
  UsersIcon, Cog6ToothIcon, DocumentTextIcon, InformationCircleIcon,
  PhotoIcon, PaintBrushIcon, ComputerDesktopIcon, CloudIcon,
  GlobeAltIcon, ServerIcon, CommandLineIcon, Squares2X2Icon,
} from '@heroicons/react/24/outline'

const consoleIcons = {
  home: HomeIcon, play: PlayCircleIcon, video: VideoCameraIcon,
  messages: ChatBubbleLeftRightIcon, users: UsersIcon, settings: Cog6ToothIcon,
  document: DocumentTextIcon, info: InformationCircleIcon, photo: PhotoIcon,
  paint: PaintBrushIcon, desktop: ComputerDesktopIcon, cloud: CloudIcon,
  globe: GlobeAltIcon, server: ServerIcon, command: CommandLineIcon, grid: Squares2X2Icon,
}

export type IconName = keyof typeof consoleIcons | 'sun' | 'moon' | 'user' | 'lock-closed' | 'eye' | 'eye-slash' | 'arrow-right' | 'chevron-down'

export function Icon({ name, className = 'size-4' }: { name: IconName; className?: string }) {
  if (name in consoleIcons) {
    const Component = consoleIcons[name as keyof typeof consoleIcons]
    return <Component className={className} aria-hidden="true" />
  }
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true" focusable="false">
      <use href={`/ui-icons.svg#${name}`} />
    </svg>
  )
}
