// Targets/Integrations 域 API
import { http } from '@/utils/request'
import type { Version } from '@/types/target'

export const targetsApi = {
  versions: () => http.get<Version[]>('/api/versions'),
}

export default targetsApi
