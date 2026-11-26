# Business rules

## R-02486486

WHEN Subtotal [Calculator!B6] is calculated THE SYSTEM SHALL set Subtotal [Calculator!B6] to (Quantity [Calculator!B2] times Unit price [Calculator!B3]).

Source: Calculator!B6, Calculator!B2, Calculator!B3

## R-805f7c28

WHEN Quantity [Calculator!B2] is at least Bulk threshold (units) [Calculator!E2] THE SYSTEM SHALL set Discount [Calculator!B7] to (Subtotal [Calculator!B6] times Bulk discount rate [Calculator!E3]) rounded to 2 decimals (half away from zero). OTHERWISE THE SYSTEM SHALL set Discount [Calculator!B7] to 0.

Source: Calculator!B7, Calculator!B2, Calculator!E2, Calculator!B6, Calculator!E3

## R-f140cd0d

WHEN Net goods [Calculator!B8] is calculated THE SYSTEM SHALL set Net goods [Calculator!B8] to (Subtotal [Calculator!B6] minus Discount [Calculator!B7]).

Source: Calculator!B8, Calculator!B6, Calculator!B7

## R-5f32fa17

WHEN Quantity [Calculator!B2] is greater than 50 THE SYSTEM SHALL set Delivery fee [Calculator!B9] to 0. OTHERWISE THE SYSTEM SHALL set Delivery fee [Calculator!B9] to (Base delivery fee [Calculator!E4] plus (MAX(0, (Delivery distance (km) [Calculator!B4] minus Free delivery within (km) [Calculator!E5])) times Fee per extra km [Calculator!E6])) rounded to 2 decimals (half away from zero).

Source: Calculator!B9, Calculator!B2, Calculator!E4, Calculator!B4, Calculator!E5, Calculator!E6

## R-a7324324

WHEN VAT [Calculator!B10] is calculated THE SYSTEM SHALL set VAT [Calculator!B10] to ((Net goods [Calculator!B8] plus Delivery fee [Calculator!B9]) times VAT rate [Calculator!E7]) rounded to 2 decimals (half away from zero).

Source: Calculator!B10, Calculator!B8, Calculator!B9, Calculator!E7

## R-794f519c

WHEN Total [Calculator!B11] is calculated THE SYSTEM SHALL set Total [Calculator!B11] to ((Net goods [Calculator!B8] plus Delivery fee [Calculator!B9]) plus VAT [Calculator!B10]).

Source: Calculator!B11, Calculator!B8, Calculator!B9, Calculator!B10
