import unittest
import os
import sys

sys.path.append(os.path.abspath('src'))

class TestSummaryCardsContract(unittest.TestCase):
    def test_order_summary_contract(self):
        print("\nVerifying Order Summary Card Contract...")
        with open('src/templates/order/view.html', 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn('data-hook="order-summary-card"', content, "Missing Order Summary Card hook")
            self.assertIn("t('order.summary.title')", content, "Missing i18n title")
            # Ensure no raw style/script in proximity (simple check)
            self.assertFalse('style=' in content.split('order-summary-card')[1].split('endcall')[0], "Inline style detected in summary card")

    def test_task_summary_contract(self):
        print("\nVerifying Task Summary Card Contract...")
        with open('src/templates/production/view.html', 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn('data-hook="task-summary-card"', content, "Missing Task Summary Card hook")
            self.assertIn("t('production.summary.title')", content, "Missing i18n title")
             # Ensure no raw style/script in proximity
            self.assertFalse('style=' in content.split('task-summary-card')[1].split('endcall')[0], "Inline style detected in summary card")

    def test_read_only_enforcement(self):
        print("\nVerifying Summary Cards Read-Only Status...")
        # Neither card should contain form inputs (name=)
        with open('src/templates/order/view.html', 'r', encoding='utf-8') as f:
            card_content = f.read().split('data-hook="order-summary-card"')[1].split('{% endcall %}')[0]
            self.assertNotIn('name=', card_content, "Order summary should be read-only")

        with open('src/templates/production/view.html', 'r', encoding='utf-8') as f:
            card_content = f.read().split('data-hook="task-summary-card"')[1].split('{% endcall %}')[0]
            self.assertNotIn('name=', card_content, "Task summary should be read-only")

        print("PASSED: Summary Cards are pure read-only components.")

if __name__ == "__main__":
    unittest.main()
