/* Application configuration values for the GestureLink LED command interface. */
#ifndef APP_CONFIG_H
#define APP_CONFIG_H

#define APP_LED_GPIO                 38U
#define APP_UART_CONSOLE_TX_GPIO     43U
#define APP_UART_CONSOLE_RX_GPIO     44U
#define APP_UART_CONSOLE_BAUD_HZ     115200U
#define APP_COMMAND_LINE_CAPACITY    32U
#define APP_COMMAND_BUFFER_SIZE      (APP_COMMAND_LINE_CAPACITY + 1U)

#endif /* APP_CONFIG_H */
