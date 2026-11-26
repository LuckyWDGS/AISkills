function main(config) {
  const groupName = 'Claude-AI';
  const listenerName = 'claude-ai-local';
  const domains = ["claude.ai", "claude.com", "anthropic.com", "claudeusercontent.com", "claudemcpcontent.com"];
  const domainPattern = '(^|[.])(' + domains.map(domain => domain.replaceAll('.', '[.]')).join('|') + ')$';
  const processPattern = '(?i)[/\\\\]AnthropicPBC[.]Claude_[^/\\\\]+[/\\\\](?:.*[/\\\\])?(?:claude|chrome-native-host|claude-make-data-folder|claude-ssh-askpass|claude-ssh-broker|claude-ssh-proxy|cowork-svc|github-mcp-server)[.]exe$';
  const domainMatch = 'DOMAIN-REGEX,' + domainPattern;
  const processMatch = 'PROCESS-PATH-REGEX,' + processPattern;
  const addedRules = [
    'AND,((NETWORK,UDP),(OR,((' + domainMatch + '),(' + processMatch + ')))),REJECT',
    processMatch + ',' + groupName,
    domainMatch + ',' + groupName,
  ];

  const groups = config['proxy-groups'] || [];
  const listeners = config.listeners || [];
  const dns = config.dns || {};
  if (groups.some(group => group.name === groupName) ||
      listeners.some(listener => listener.name === listenerName || Number(listener.port) === 17891) ||
      (dns.listen && !['127.0.0.2:53', '127.0.0.1:1053'].includes(dns.listen))) {
    throw new Error('Claude-AI conflicts with an existing group, listener, or DNS bind address');
  }

  config['proxy-groups'] = [...groups, {
    name: groupName,
    type: 'select',
    proxies: ['REJECT'],
    'default-selected': 'REJECT',
    'include-all': true,
    'exclude-type': 'Direct|Compatible|RejectDrop|Pass',
    'empty-fallback': 'REJECT',
  }];
  config.listeners = [...listeners, {
    name: listenerName, type: 'mixed', listen: '127.0.0.1', port: 17891,
    udp: false, proxy: groupName,
  }];
  config['find-process-mode'] = 'always';
  config.rules = [...addedRules, ...(config.rules || [])];

  const policy = { ...(dns['nameserver-policy'] || {}) };
  for (const domain of domains) {
    for (const key of [domain, '+.' + domain]) {
      policy[key] = ['https://1.1.1.1/dns-query#' + groupName, 'https://9.9.9.9/dns-query#' + groupName];
    }
  }
  config.dns = { ...dns, enable: true, listen: '127.0.0.2:53', 'nameserver-policy': policy };
  if (dns['enhanced-mode'] === 'fake-ip' && (!dns['fake-ip-filter-mode'] || dns['fake-ip-filter-mode'] === 'blacklist')) {
    config.dns['fake-ip-filter'] = [...new Set([...(dns['fake-ip-filter'] || []), ...domains.map(domain => '+.' + domain)])];
  }
  return config;
}
