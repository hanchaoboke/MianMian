export const interviewStyles = [
  {value: 'HARDCORE', label: '深挖型'},
  {value: 'GUIDING', label: '引导型'},
  {value: 'BUSINESS', label: '业务型'},
  {value: 'CREATIVE', label: '天马行空型'},
  {value: 'ALL_ROUND', label: '全能型 · 高难度'},
]
export const styleName = value => interviewStyles.find(style => style.value === value)?.label || value
