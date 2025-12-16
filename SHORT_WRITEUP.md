# Technical Write-Up: Badminton Court Booking System

## Database Design

The system uses a normalized relational database schema with eight core models. The **Court**, **Equipment**, and **Coach** models represent the bookable resources. **CoachAvailability** defines weekly recurring schedules using day-of-week integers (0-6) and time ranges, providing flexibility without storing individual dates.

The **Booking** model serves as the central transaction record, linking users to courts with optional coaches. It stores both `base_price` and `total_price` along with a JSON `price_breakdown` field that captures the complete pricing calculation for audit purposes. The **BookingEquipment** through-table enables many-to-many relationships with quantity tracking, allowing multiple equipment types per booking.

**PricingRule** implements a priority-based configuration system where rules are ordered and applied sequentially. Each rule can be either percentage-based (multiplier) or flat-fee, with optional time and day constraints. This design eliminates hardcoded pricing logic entirely.

The **Waitlist** model implements a FIFO queue using `created_at` timestamps. It tracks three states: WAITING, NOTIFIED, and EXPIRED. The composite index on `(court, date, start_time, end_time, status)` ensures efficient queue queries. When a booking is cancelled, the system automatically queries this index to find the next waiting user.

**Concurrent booking prevention** is achieved through Django's `select_for_update()`, which acquires a database-level row lock on the court during the transaction. This prevents race conditions when multiple users simultaneously attempt to book the same slot. If a conflict is detected, the system offers waitlist enrollment instead of failing silently.

## Pricing Engine Approach

The pricing engine is completely data-driven, with zero hardcoded business logic. It operates in three phases: base price retrieval, rule application, and breakdown generation.

During rule application, the engine queries enabled `PricingRule` objects ordered by priority. For each rule, it evaluates applicability based on time constraints (`start_time`/`end_time`) and day constraints (`applies_to_days`). Percentage rules compound on the current price, while flat fees are added directly. For example, a ₹500 base price with 20% indoor premium becomes ₹600, then a 50% peak hour multiplier applies to ₹600 (not ₹500), yielding ₹900.

Equipment and coach fees are handled through dedicated rule types that reference the actual resource costs. The `EQUIPMENT_FEE` rule type uses the flat fee from the rule configuration, while `COACH_FEE` dynamically pulls the coach's `hourly_fee`. This separation allows administrators to adjust pricing without code changes.

The complete calculation is stored as JSON in each booking's `price_breakdown` field, creating an immutable audit trail. This design ensures pricing transparency and enables historical analysis of pricing rule effectiveness.

The modular service layer (`AvailabilityService`, `PricingEngine`, `WaitlistService`) separates business logic from views, making the codebase testable and maintainable. All database operations use atomic transactions to guarantee consistency, ensuring that partial bookings never occur even under high concurrent load.
