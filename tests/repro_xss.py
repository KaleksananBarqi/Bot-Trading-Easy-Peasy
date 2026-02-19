
import unittest
import html

class TestDashboardSecurity(unittest.TestCase):
    def test_html_injection(self):
        # Simulation of the vulnerable code logic
        day_num = 15
        
        # Scenario: somehow a string payload got through (e.g. invalid type handling upstream)
        pnl_text = "<script>alert('XSS')</script>"
        card_class = "neutral"
        
        # The vulnerable f-string
        html_output = f"""
                <div class='day-card {card_class}'>
                    <div class='day-date'>{day_num}</div>
                    <div class='day-pnl'>{pnl_text}</div>
                </div>
                """
        
        # Check if the script tag is present verbatim (Vulnerable)
        if "<script>" in html_output:
            print("\nVULNERABILITY CONFIRMED: Script tag found in output.")
        else:
            print("\nSECURE: Script tag was not found (escaped?).")
            
        self.assertIn("<script>", html_output, "HTML should contain script tag in vulnerable version")

    def test_html_fix(self):
        # Simulation of the fixed code logic
        day_num = 15
        pnl_text = "<script>alert('XSS')</script>"
        card_class = "neutral"
        
        # The fixed f-string using html.escape
        html_output = f"""
                <div class='day-card {card_class}'>
                    <div class='day-date'>{day_num}</div>
                    <div class='day-pnl'>{html.escape(str(pnl_text))}</div>
                </div>
                """
        
        # Check if the script tag is escaped (Secure)
        print(f"\nFixed Output: {html_output}")
        self.assertNotIn("<script>", html_output, "HTML should NOT contain raw script tag in fixed version")
        self.assertIn("&lt;script&gt;", html_output, "HTML should contain escaped script tag")

if __name__ == '__main__':
    unittest.main()
