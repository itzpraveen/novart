class AppConfig {
  static const apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://erp.novartarchitects.com/api/v1/',
  );

  static const appName = 'Novart ERP';
}
