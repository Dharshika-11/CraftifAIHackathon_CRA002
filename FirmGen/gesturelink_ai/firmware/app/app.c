/* Application startup and UART command loop for the GestureLink LED. */
#include "app.h"

#include "app_config.h"
#include "board.h"
#include "gesture_platform.h"
#include "gesture_service.h"
#include "logger.h"

static const char tag[] = "gesture_app";

void app_start(void)
{
    const gesture_io_t *io = gesture_platform_io();

    ESP_LOGI(tag, "Starting %s", board_name());
    ESP_LOGI(tag, "Command UART: TX GPIO %u, RX GPIO %u at %u baud",
             (unsigned int)APP_UART_CONSOLE_TX_GPIO,
             (unsigned int)APP_UART_CONSOLE_RX_GPIO,
             (unsigned int)APP_UART_CONSOLE_BAUD_HZ);

    if (!gesture_service_run(io))
    {
        ESP_LOGE(tag, "LED initialization or command service setup failed");
    }
}
