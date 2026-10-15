/* ESP-IDF GPIO adapter and bounded command-line reader for the UART console. */
#include "gesture_platform.h"

#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>

#include "app_config.h"
#include "board.h"
#include "driver/gpio.h"
#include "esp_err.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "gesture_io.h"

static const char tag[] = "gesture_platform";
static bool skip_line_feed_after_carriage_return;

/* Apply a logical LED state through the board's active-level mapping. */
static bool gesture_platform_set_led(bool is_on)
{
    esp_err_t status = gpio_set_level((gpio_num_t)BOARD_LED_GPIO, board_led_level(is_on));

    if (status != ESP_OK)
    {
        ESP_LOGE(tag, "LED output update failed: %s", esp_err_to_name(status));
        return false;
    }

    return true;
}

/* Initialize the GPIO output before any UART command is accepted. */
static bool gesture_platform_initialize_led(void)
{
    const gpio_config_t led_config = {
        .pin_bit_mask = (1ULL << BOARD_LED_GPIO),
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE
    };
    esp_err_t status = gpio_config(&led_config);

    if (status != ESP_OK)
    {
        ESP_LOGE(tag, "LED GPIO setup failed: %s", esp_err_to_name(status));
        return false;
    }

    return gesture_platform_set_led(false);
}

/* Read through console stdio, waiting for a complete line and draining overflow. */
static bool gesture_platform_read_line(char *buffer, size_t capacity, size_t *length)
{
    size_t count = 0U;
    bool overflow = false;
    bool line_complete = false;
    int input_character;

    if ((buffer == NULL) || (length == NULL) || (capacity < 2U))
    {
        return false;
    }

    while (!line_complete)
    {
        input_character = getchar();
        if (input_character == EOF)
        {
            vTaskDelay(1U);
            continue;
        }

        if (skip_line_feed_after_carriage_return)
        {
            skip_line_feed_after_carriage_return = false;
            if (input_character == '\n')
            {
                continue;
            }
        }

        if ((input_character == '\n') || (input_character == '\r'))
        {
            skip_line_feed_after_carriage_return = (input_character == '\r');
            line_complete = true;
        }
        else if (count < (capacity - 1U))
        {
            buffer[count] = (char)input_character;
            count++;
        }
        else
        {
            overflow = true;
        }
    }

    buffer[count] = '\0';
    *length = overflow ? capacity : count;

    if (overflow)
    {
        ESP_LOGW(tag, "Rejected command line exceeding %u bytes", (unsigned int)(capacity - 1U));
    }

    return true;
}

/* Report each command outcome over the UART console's configured logging path. */
static void gesture_platform_report_command(bool accepted, const char *command)
{
    if (accepted)
    {
        ESP_LOGI(tag, "Command accepted: %s", command);
    }
    else
    {
        ESP_LOGW(tag, "Command rejected: %s", command);
    }
}

static const gesture_io_t gesture_platform_callbacks = {
    .initialize_led = gesture_platform_initialize_led,
    .set_led = gesture_platform_set_led,
    .read_line = gesture_platform_read_line,
    .report_command = gesture_platform_report_command
};

bool gesture_platform_init(void)
{
    return gesture_platform_initialize_led();
}

const gesture_io_t *gesture_platform_io(void)
{
    return &gesture_platform_callbacks;
}
